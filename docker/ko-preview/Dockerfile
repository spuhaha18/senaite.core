# Preview image: official SENAITE 2.6.0 runtime + this fork's senaite.core
# source (incl. Korean translations) + current GitHub sources of the add-ons.
# Build from the repository root:
#   docker build -f docker/ko-preview/Dockerfile -t senaite-ko-preview .
FROM senaite/senaite:v2.6.0
ARG EGGS=/home/senaite/senaitelims/eggs/cp27mu
USER root
RUN apt-get update -qq && apt-get install -y -qq git >/dev/null || true
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
RUN find $EGGS/senaite.core-2.6.0-py2.7.egg -name "*.mo" -delete
