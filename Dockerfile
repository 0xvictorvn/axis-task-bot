FROM python:3.9-slim

WORKDIR /app

# In log ra màn hình Render ngay lập tức
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render tự động ép cổng PORT, dòng này chỉ để dự phòng
ENV PORT=8080
EXPOSE 8080

CMD ["python", "axis_task_alert.py"]
