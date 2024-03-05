FROM python:3.9-slim-buster

WORKDIR /app

COPY main.py /usr/bin/chart-util
COPY requirements.txt /tmp/requirements.txt

RUN set -xe;\
    apt-get update;\
    apt-get install -y \
      git \
      curl \
      bash \
    ;\
    apt-get clean;\
    rm -rf /var/lib/apt/lists/*;\
    curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash;\
    pip3 install -r /tmp/requirements.txt

ENTRYPOINT ["/usr/bin/chart-util"]
