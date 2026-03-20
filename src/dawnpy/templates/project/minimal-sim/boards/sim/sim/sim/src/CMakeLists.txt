# SPDX-License-Identifier: Apache-2.0

if(CONFIG_BOARDCTL)
  list(APPEND SRCS sim_appinit.c)
endif()

list(APPEND SRCS sim_bringup.c)

target_sources(board PRIVATE ${SRCS})

if(CONFIG_DAWN_FAKE_DRIVERS)
  target_link_libraries(board PRIVATE board_common)
endif()
