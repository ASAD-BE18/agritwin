#pragma once

// Shared safety logic + serial protocol for both the hardware and sim builds.
// See docs/team-briefs/IRFAN.md for the full spec this implements.
// Owner: Muhammad Irfan.

void coreSetup();
void coreLoop();
