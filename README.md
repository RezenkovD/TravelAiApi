# FastAPI Travel Recommendations Service

## Installation and Running

### 1. Clone the repository

```bash
git clone https://github.com/RezenkovD/TravelAiApi
cd TravelAiApi/
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Export environment variables

```bash
export OPENAI_API_KEY=your_openai_api_key
```

### 5. Run the server

```bash
uvicorn main:app --reload
```

---

The service will be available at: [http://127.0.0.1:8000](http://127.0.0.1:8000)
