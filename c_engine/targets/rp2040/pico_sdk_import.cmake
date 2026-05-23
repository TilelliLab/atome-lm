# pico_sdk_import.cmake — official import shim from the Pico SDK README.
#
# Vendored verbatim so this directory builds without copying SDK files
# manually. Resolves PICO_SDK_PATH from env or CMake var.
if (DEFINED ENV{PICO_SDK_PATH} AND (NOT PICO_SDK_PATH))
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
    message("Using PICO_SDK_PATH from environment ('${PICO_SDK_PATH}')")
endif ()

if (NOT PICO_SDK_PATH)
    message(FATAL_ERROR
        "Set PICO_SDK_PATH (env or -DPICO_SDK_PATH=...). "
        "Get the SDK with: git clone --depth 1 https://github.com/raspberrypi/pico-sdk")
endif ()

get_filename_component(PICO_SDK_PATH "${PICO_SDK_PATH}" REALPATH BASE_DIR "${CMAKE_BINARY_DIR}")
if (NOT EXISTS ${PICO_SDK_PATH})
    message(FATAL_ERROR "PICO_SDK_PATH '${PICO_SDK_PATH}' does not exist")
endif ()

set(PICO_SDK_INIT_CMAKE_FILE ${PICO_SDK_PATH}/pico_sdk_init.cmake)
if (NOT EXISTS ${PICO_SDK_INIT_CMAKE_FILE})
    message(FATAL_ERROR "${PICO_SDK_INIT_CMAKE_FILE} not found")
endif ()

set(PICO_SDK_PATH ${PICO_SDK_PATH} CACHE PATH "Path to the Raspberry Pi Pico SDK" FORCE)
include(${PICO_SDK_INIT_CMAKE_FILE})
