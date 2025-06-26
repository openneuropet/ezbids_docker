FROM neurodebian:nd20.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y

RUN apt update && apt install -y parallel python3 python3-pip tree curl unzip git jq python libgl-dev python-numpy bc

RUN pip3 install numpy==1.23.0 nibabel==4.0.0 pandas matplotlib pyyaml==5.4.1 pydicom==2.3.1 natsort pydeface && \
    pip3 install quickshear mne mne-bids pypet2bids==1.4.1

# Install pypet2bids
#RUN git clone https://github.com/openneuropet/PET2BIDS && \
#    cd PET2BIDS && make installpoetry buildpackage installpackage

RUN apt-get install -y build-essential pkg-config cmake git pigz rename zstd libopenjp2-7 libgdcm-tools wget libopenblas-dev && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

RUN touch /.pet2bidsconfig && chown 1001:1001 /.pet2bidsconfig

RUN echo "DEFAULT_METADATA_JSON=/usr/local/lib/python3.8/dist-packages/pypet2bids/template_json.json" > /.pet2bidsconfig

RUN mkdir -p /usr/local/fsl && \
    git clone https://github.com/dlevitas/FSL_binaries /usr/local/fsl && \
    rm -rf /usr/local/fsl/README.md && \
    mkdir -p /usr/local/fsl/data/standard && \
    mv /usr/local/fsl/bin/MNI152_T1_2mm_brain.nii.gz /usr/local/fsl/data/standard

ENV FSLDIR=/usr/local/fsl
ENV PATH=$PATH:$FSLDIR/bin
ENV FSLOUTPUTTYPE=NIFTI_GZ

RUN apt-get update \
    && apt-get install -y ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

ARG NODE_MAJOR=20
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

RUN apt-get update \
    && apt-get install nodejs -y

RUN cd /tmp && curl -fLO https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_lnx.zip \
    && unzip /tmp/dcm2niix_lnx.zip \
    && mv dcm2niix /usr/local/bin

RUN mkdir -p /app

# Get bids-specification from github
RUN cd /app && git clone https://github.com/bids-standard/bids-specification && \
    cd bids-specification && git checkout 3537e9edbc81545614d3ee605c398361099b6977

#install ROBEX
ADD https://www.nitrc.org/frs/download.php/5994/ROBEXv12.linux64.tar.gz//?i_agree=1&download_now=1 /
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH /ROBEX:$PATH

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/v$NODE_VERSION/bin:$PATH

#install bids-validator
RUN npm install -g npm@9.5.1
RUN npm install -g bids-validator@1.14.8
RUN git clone https://github.com/bids-standard/bids-validator

# move copy to last step to save time on container rebuilding
COPY . /app

# Install everything in the API folder as well
WORKDIR /app/api
RUN cp /app/package.json /app/api/ && npm install
RUN npx tsc

# install source code from local
WORKDIR /app/handler
RUN npm -g install pm2
RUN npm install
RUN npx tsc
