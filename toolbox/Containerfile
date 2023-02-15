FROM registry.fedoraproject.org/fedora:37
LABEL name="rdo-toolbox"

COPY extra-packages /
RUN dnf -y install $(<extra-packages) && dnf clean all
RUN rm /extra-packages

COPY requirements.txt /
RUN pip install -r /requirements.txt
RUN rm /requirements.txt

COPY etc /etc/
COPY etc/profile.d /etc/profile.d

RUN git clone https://github.com/rdo-infra/releng/ /releng
