import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionUserMessageParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from database import get_async_session, init_db
from models import TravelRequest
from schemas import ExcludeUpdate, TravelRequestIn, TravelRequestOut

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/recommendations/", response_model=TravelRequestOut)
async def create_recommendation(
    request: TravelRequestIn,
    session: AsyncSession = Depends(get_async_session),
):
    if request.num_places < 1:
        raise HTTPException(status_code=400, detail="num_places must be >= 1")

    try:
        places = await generate_places(request)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    db_request = TravelRequest(
        text=request.text,
        exclude=request.exclude,
        num_places=request.num_places,
        response_json=places,
        created_at=datetime.now(),
    )
    session.add(db_request)
    await session.commit()
    await session.refresh(db_request)
    return db_request


@app.post("/recommendations/{request_id}/exclude", response_model=TravelRequestOut)
async def refine_recommendation(
    request_id: int,
    exclude_update: ExcludeUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    exclude = exclude_update.exclude.strip()

    db_request = (
        await session.execute(
            select(TravelRequest).where(TravelRequest.id == request_id)
        )
    ).scalar_one_or_none()

    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")

    prev_exclude = db_request.exclude or ""
    combined_exclude = (prev_exclude + " " + exclude).strip()

    try:
        new_request = TravelRequestIn(
            text=db_request.text,
            num_places=db_request.num_places,
            exclude=combined_exclude,
        )
        places = await generate_places(new_request)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    refined_request = TravelRequest(
        text=db_request.text,
        exclude=combined_exclude,
        num_places=db_request.num_places,
        response_json=places,
        created_at=datetime.now(),
    )
    session.add(refined_request)
    await session.commit()
    await session.refresh(refined_request)
    return refined_request


@app.get("/history", response_model=list[TravelRequestOut])
async def get_history(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(TravelRequest))
    requests = result.scalars().all()
    return requests


@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(OpenAIError),
)
async def generate_places(request: TravelRequestIn) -> list[dict[str, Any]]:
    exclude_str = f"(Without {request.exclude})" if request.exclude else ""
    prompt = (
        f"I am a tourist. {request.text}.\n"
        f"Generate exactly {request.num_places} places to visit {exclude_str}. "
        "The response format must be a JSON array of objects: "
        '[{ "name": string, "description": string, "coords": {"lat": float, "lng": float} }]'
    )

    try:
        messages: list[ChatCompletionUserMessageParam] = [
            {"role": "user", "content": prompt}
        ]
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
        )

        content = response.choices[0].message.content

        parsed = json.loads(content)

        if not isinstance(parsed, list) or len(parsed) != request.num_places:
            raise ValueError(
                "Invalid response from OpenAI: number of places does not match."
            )

        return parsed

    except OpenAIError as e:
        raise ValueError(f"OpenAI API error: {str(e)}")
    except json.JSONDecodeError:
        raise ValueError("OpenAI returned invalid JSON.")
