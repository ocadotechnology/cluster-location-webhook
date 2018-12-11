FROM python:3.7-alpine

COPY hook.py requirements.txt README.md LICENSE /app/
RUN pip install -r /app/requirements.txt

ENTRYPOINT ["python", "-u", "/app/hook.py"]
