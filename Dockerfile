FROM python:3.9-slim

WORKDIR /app

# THÊM DÒNG NÀY ĐỂ HIỆN LOG NGAY LẬP TỨC
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=7860
EXPOSE 7860

CMD ["python", "axis_task_alert.py"]
