# Preview image: official SENAITE 2.6.0 runtime + this fork's senaite.core
# source (incl. Korean translations) + current GitHub sources of the add-ons.
# Build from the repository root:
#   docker build -f docker/ko-preview/Dockerfile -t senaite-ko-preview .
FROM senaite/senaite:v2.6.0
ARG EGGS=/home/senaite/senaitelims/eggs/cp27mu
USER root
# Debian buster is archived: use archive.debian.org for packages.
# git: fetch add-on sources; fonts-nanum: Korean text in PDF reports
# (the stability reports of senaite.pharma are rendered by WeasyPrint)
RUN echo "deb http://archive.debian.org/debian buster main" > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update -qq \
 && apt-get install -y -qq git fonts-nanum >/dev/null \
 && fc-cache -f >/dev/null
RUN set -e; cd /tmp; \
    for r in senaite.app.listing senaite.app.spotlight senaite.impress \
             senaite.app.supermodel senaite.jsonapi senaite.lims; do \
      git clone -q --depth 1 https://github.com/senaite/$r.git; \
      sub=$(echo $r | tr . /); \
      rm -rf $EGGS/$r-2.6.0-py2.7.egg/$sub; \
      cp -r /tmp/$r/src/$sub $EGGS/$r-2.6.0-py2.7.egg/$sub; \
      rm -rf /tmp/$r; \
    done
RUN rm -rf $EGGS/senaite.core-2.6.0-py2.7.egg/bika $EGGS/senaite.core-2.6.0-py2.7.egg/senaite/core
COPY src/bika $EGGS/senaite.core-2.6.0-py2.7.egg/bika
COPY src/senaite/core $EGGS/senaite.core-2.6.0-py2.7.egg/senaite/core
COPY src/senaite/pharma $EGGS/senaite.core-2.6.0-py2.7.egg/senaite/pharma
RUN find $EGGS/senaite.core-2.6.0-py2.7.egg -name "*.mo" -delete
