/* SPDX-License-Identifier: Apache-2.0 */

#include <nuttx/config.h>
#include <nuttx/board.h>

#include "sim.h"

#ifdef CONFIG_BOARDCTL
int board_app_initialize(uintptr_t arg)
{
  return sim_bringup();
}
#endif
