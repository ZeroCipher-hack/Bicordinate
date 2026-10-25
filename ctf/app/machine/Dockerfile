# SSH "machine" masalasi. Build:  python3 ../../build.py && docker build -t bico-machine .
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server sudo \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd \
    && ssh-keygen -A \
    # operator: parol xeshi setup.env dan ENTRYPOINT'da o'rnatiladi; sudo YO'Q, boshqa foydalanuvchi faylini ko'ra olmaydi
    # Debian bazasida "operator" nomli tizim guruhi allaqachon bor (base-passwd) — shuni qayta ishlatamiz (-g),
    # aks holda useradd yangi shaxsiy guruh yaratmoqchi bo'lib to'qnashadi (exit code 9).
    && useradd -m -s /bin/bash -g operator operator \
    && sed -ri 's/^#?PermitRootLogin.*/PermitRootLogin no/; s/^#?PasswordAuthentication.*/PasswordAuthentication yes/; \
                s/^#?X11Forwarding.*/X11Forwarding no/; s/^#?AllowTcpForwarding.*/AllowTcpForwarding no/; \
                s/^#?PermitTunnel.*/PermitTunnel no/' /etc/ssh/sshd_config \
    && echo "AllowUsers operator" >> /etc/ssh/sshd_config \
    && echo "ClientAliveInterval 120" >> /etc/ssh/sshd_config \
    && echo "ClientAliveCountMax 2" >> /etc/ssh/sshd_config \
    && echo "MaxStartups 30:50:60" >> /etc/ssh/sshd_config \
    && echo "LoginGraceTime 20" >> /etc/ssh/sshd_config
COPY user.txt /home/operator/user.txt
COPY setup.env /setup.env
COPY rockyou-mini.txt /usr/share/wordlists/rockyou.txt
COPY entrypoint.sh /entrypoint.sh
RUN chmod 400 /home/operator/user.txt && chown operator:operator /home/operator/user.txt && chmod +x /entrypoint.sh
EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
