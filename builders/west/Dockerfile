FROM zmkfirmware/zmk-build-arm:stable

WORKDIR /workspace
COPY . /workspace/

RUN west init -l config
RUN west update

# Build both halves
RUN west build -d build/left -b glove80_lh
RUN west build -d build/right -b glove80_rh

# Copy firmware files to easily accessible location
RUN mkdir -p /workspace/firmware && \
  cp build/left/zephyr/zmk.uf2 /workspace/firmware/glove80_lh-zmk.uf2 && \
  cp build/right/zephyr/zmk.uf2 /workspace/firmware/glove80_rh-zmk.uf2
