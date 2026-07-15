// firmware/node/types.h
// Shared type definitions for all Juice Battle node modules.
// Every module result struct uses this Quality enum.
#pragma once

enum Quality {
    QUALITY_GOOD     = 0,
    QUALITY_DEGRADED = 1,
    QUALITY_FAILED   = 2
};
