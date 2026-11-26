# RANGER'S GAME OF TELEPHONE (2025)
A self-evolving soundscape of phone calls between houses, generated from a custom random number-based algorithm and synthesized in MaxMSP. See [here](https://ryurongliu.com/rangers-game-of-telephone) for more information.

2.0 is currently the most up-to-date version of TELEPHONE. 

HANDHELD version routes all audio to a single-output telephone handset, for quiet galleries. 

All code was written by hand. No AI was used in the creation of this work.

# Code
[Jupyter Notebook](2.0/telephone-2.0.ipynb) handles all call-routing and 'conversation' generation. It uses OSC to send frequency and amplitude CV to [telephone.maxpat](2.0/telephone.maxpat), which synthesizes the 8 different 'voices'. Python also sends commands to Arduino, controlling house lights and phone lights.

Call-routing logic is implemented in [telephone.py](2.0/telephone.py), which uses random number-based probabilities to decide who to call, how long to wait for pickup, whether to pickup, whether to redial, and how long to talk for.

'Conversation' generation is also implemented in [telephone.py](2.0/telephone.py). The algorithm approximates speech-like changes in frequency and duration, including starting and ending each conversation with hello and goodbye. It also handles switching back-and-forth between callers, with appropriate pauses in-between. 

# Call Logs

Call logs are available from two installations:
1) Base Camp Studios 2, Seattle, WA, September-December 2025: 16,213 logs
2) New Alliance Gallery, Boston, MA, September-November 2026: 85,672 logs

For convenience, logs are saved by individual voices (0-7) as well as all together.

# Video Demo

[![video demo](https://img.youtube.com/vi/Q_XGHEn4Ovk/maxresdefault.jpg)](https://www.youtube.com/watch?v=Q_XGHEn4Ovk)

