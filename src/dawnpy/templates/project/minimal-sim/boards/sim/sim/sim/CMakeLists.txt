# SPDX-License-Identifier: Apache-2.0

add_subdirectory(
  "$ENV{DAWN_BOARDS_COMMON}"
  "${CMAKE_BINARY_DIR}/boards/common"
)

add_subdirectory(src)
