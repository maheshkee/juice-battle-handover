// firmware/node/types.h
// Shared type definitions for all Juice Battle node modules.
// Every module result struct uses this Quality enum.
#pragma once

enum Quality {
    GOOD     = 0,
    DEGRADED = 1,
    FAILED   = 2
};
