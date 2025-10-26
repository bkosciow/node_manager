FROM python:3.10
ARG PUID
ARG GUID

RUN apt update && apt upgrade -y && apt install -y --no-install-recommends supervisor sudo cron
RUN mkdir -p \
    /var/log/supervisord \
    /var/run/supervisord \
;

RUN useradd -u ${PUID} -m app

COPY docker/supervisord.conf /
COPY docker/crontab /
RUN crontab -u app /crontab

RUN mkdir /app
RUN mkdir /scan
RUN mkdir /jellyfin
RUN mkdir /supervisordlog

WORKDIR /app
COPY . /app/
RUN pip install -r /app/requirements.txt
EXPOSE 5000

RUN mkdir /cronlog && chmod 0777 /cronlog

CMD ["/usr/bin/supervisord", "-c", "/supervisord.conf"]
