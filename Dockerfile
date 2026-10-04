FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HR_DATABASE=/data/hr.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 hr \
    && useradd --uid 10001 --gid hr --no-create-home hr \
    && mkdir -p /data && chown hr:hr /data
COPY --chown=hr:hr . .
USER 10001:10001
EXPOSE 8000
CMD ["sh", "scripts/start.sh"]
