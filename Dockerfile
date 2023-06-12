FROM docker.io/library/python:3.11-bullseye
RUN mkdir -p "/app/index"  \
    &&  mkdir -p "/app/static" \
    &&  mkdir -p "/app/searchResults"
WORKDIR /app
COPY .  /app/
RUN apt-get update && apt-get install -y build-essential
RUN python3 -m pip install -r requirements.txt
RUN which python3
EXPOSE 5008
CMD ["/usr/local/bin/python3","talentBot.py"]
