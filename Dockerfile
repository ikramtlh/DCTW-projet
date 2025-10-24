FROM python:3.13.6

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5003

CMD ["python", "server.py"]
