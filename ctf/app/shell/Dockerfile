# O'quvchi terminali. Build:  python3 ../../build.py && docker build -t bico-shell .
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash coreutils findutils grep sed gawk binutils xxd bsdextrautils unzip zip john nano less file \
      openssl python3 procps ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash talaba
COPY masalalar /opt/masalalar
COPY bashrc /etc/bico.bashrc
COPY rockyou-mini.txt /usr/share/wordlists/rockyou.txt
USER talaba
WORKDIR /home/talaba
ENTRYPOINT ["/bin/bash", "--rcfile", "/etc/bico.bashrc", "-i"]
