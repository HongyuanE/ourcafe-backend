# Container image for AWS Lambda. The AWS base image bundles the Lambda Runtime
# Interface, so the same FastAPI app (adapted by Mangum in app/main.py) runs as a
# Lambda function. Local HTTP development does NOT use this image — use
# `make run` (uvicorn) for that; this image is the deploy artifact, built in CI.
FROM public.ecr.aws/lambda/python:3.12

# Install dependencies into the Lambda task root.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t "${LAMBDA_TASK_ROOT}"

# Application code.
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Stamp the build with its git commit so `/` and `/info` can report what's live.
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

# Lambda handler: "<module path>.<callable>" — Mangum adapter exported as `handler`.
CMD ["app.main.handler"]
