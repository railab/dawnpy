/* SPDX-License-Identifier: Apache-2.0 */

#ifndef __DAWN_OOT_PROJECT_SIM_H
#define __DAWN_OOT_PROJECT_SIM_H

#include <nuttx/config.h>

#include "fake_drivers.h"

#define SIM_PROCFS_MOUNTPOINT "/proc"

int sim_bringup(void);

#endif
