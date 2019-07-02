FROM python:3-alpine

WORKDIR /build

COPY . .

RUN pip install -r requirements.txt

ENV SLACK_TOKEN='SET_THIS'
ENV DRY_RUN=true

CMD SLACK_TOKEN=${SLACK_TOKEN} \
  DRY_RUN=${DRY_RUN} \
  python slack_autoarchive.py
