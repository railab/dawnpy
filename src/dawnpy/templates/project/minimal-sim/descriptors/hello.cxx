// SPDX-License-Identifier: Apache-2.0

#include "dawn/common/descriptor.hxx"

#include "dawn/io/buttons.hxx"
#include "dawn/io/leds.hxx"
#include "dawn/io/uuid.hxx"
#include "dawn/proto/shell/pretty.hxx"

using namespace dawn;

#define LEDS1     CIOLeds::objectId(false, 0)
#define BUTTONS1  CIOButtons::objectId(false, 0)
#define UUID1     CIOUuid::objectId(0)
#define SHELL1    CProtoShellPretty::objectId(0)

uint32_t g_dawn_desc[] =
{
  CDescriptor::DAWN_DESCRIPTOR_HDR, 5,

  CDescriptor::objectId(1), 2,
    CDescriptor::cfgIdVersion(), 0x00010000,
    CDescriptor::cfgIdString(2),
      0x696e696d,
      0x006d6973,

  LEDS1, 1,
    CIOCommon::cfgIdDevno(), 0,

  BUTTONS1, 1,
    CIOCommon::cfgIdDevno(), 0,

  UUID1, 0,

  SHELL1, 1,
    CProtoShellPretty::cfgIdIOBind(3),
      LEDS1,
      BUTTONS1,
      UUID1,

  CDescriptor::DAWN_DESCRIPTOR_FOOT,
    0xdeadbeef
};

size_t g_dawn_desc_size = sizeof(g_dawn_desc);
