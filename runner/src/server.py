import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .static_check import ast_static_check

app = FastAPI()

PYTHON_EXEC = os.environ.get("PYTHON_EXECUTABLE", "python3")
STATIC_CHECK = os.environ.get("STATIC_CHECK", "false").lower() == "true"
TIMEOUT = int(os.environ.get("TIMEOUT", "10"))

class CodeRequest(BaseModel):
    code: str

@app.post("/run-code")
async def run_code_executor(request_data: CodeRequest):
    code = request_data.code

    if STATIC_CHECK:
        static_issues = ast_static_check(code)
        if static_issues:
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'forbidden constructs found',
                    'details': static_issues
                }
            )

    try:
        result = subprocess.run(
            [PYTHON_EXEC, "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )

        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode,
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail='execution timed out')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))