FROM centos:latest
LABEL maintainer="Mark Howison <mhowison@brown.edu>"
LABEL repository="browndatascience"
LABEL image="georeg"
LABEL version="0.0.1"

RUN yum update -y
RUN yum install -y \
  bzip2 \
  sudo \
  unzip \
  wget \
  which \
  zip

RUN yum clean all

RUN useradd -m -d /home/georeg -s /bin/bash georeg
RUN echo "georeg ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/georeg \
 && chmod 0440 /etc/sudoers.d/georeg

USER georeg
ENV HOME /home/georeg

RUN cd /home/georeg \
 && wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh \
 && bash Miniconda2-latest-Linux-x86_64.sh -b \
 && rm Miniconda2-latest-Linux-x86_64.sh

ENV PATH /home/georeg/miniconda2/bin:$PATH

RUN conda install -y -c brown-data-science georeg
RUN conda clean -ay

ENTRYPOINT ["/home/georeg/miniconda2/bin/georeg"]
