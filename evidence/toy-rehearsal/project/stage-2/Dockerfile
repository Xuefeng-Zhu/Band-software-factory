FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html style.css app.js ./
USER 65534:65534
ENV PORT=8080
EXPOSE 8080
CMD ["python", "server.py"]
