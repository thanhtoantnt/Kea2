FROM eclipse-temurin:17-jdk-jammy

ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV NDK_VERSION=25.2.9519653
ENV NDK_ROOT=/opt/android-sdk/ndk/25.2.9519653
ENV ANDROID_NDK_HOME=/opt/android-sdk/ndk/25.2.9519653
ENV PATH=/opt/android-sdk/cmake/3.18.1/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        ccache \
        curl \
        file \
        findutils \
        git \
        make \
        ninja-build \
        unzip \
        zsh \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p "${ANDROID_HOME}/cmdline-tools" \
    && curl --retry 5 --retry-delay 5 --retry-all-errors -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip \
    && unzip -q /tmp/cmdline-tools.zip -d /tmp/android-cmdline-tools \
    && mv /tmp/android-cmdline-tools/cmdline-tools "${ANDROID_HOME}/cmdline-tools/latest" \
    && rm -rf /tmp/cmdline-tools.zip /tmp/android-cmdline-tools

RUN yes | sdkmanager --licenses >/dev/null || true \
    && for attempt in 1 2 3; do \
        yes | sdkmanager \
            "platform-tools" \
            "platforms;android-32" \
            "build-tools;35.0.0" \
            "ndk;25.2.9519653" \
            "cmake;3.18.1" \
        && break; \
        rc="$?"; \
        if [ "$attempt" = 3 ]; then exit "$rc"; fi; \
        rm -rf "${ANDROID_HOME}/.temp" /tmp/PackageOperation*; \
        sleep "$((attempt * 10))"; \
    done \
    && test -x "${ANDROID_HOME}/build-tools/35.0.0/d8" \
    && test -x "${ANDROID_HOME}/cmake/3.18.1/bin/cmake" \
    && test -f "${NDK_ROOT}/build/cmake/android.toolchain.cmake" \
    && test -f "${ANDROID_HOME}/platforms/android-32/android.jar"

WORKDIR /workspace/android
