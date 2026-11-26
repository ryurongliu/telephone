# RANGER'S GAME OF TELEPHONE
A self-evolving soundscape of phone calls between houses, generated from a custom random number-based algorithm and synthesized in MaxMSP. See [here](https://ryurongliu.com/rangers-game-of-telephone) for more information.

2.0 is currently the most up-to-date version of TELEPHONE. 

All code was written by hand. No AI was used in the creation of this work.

# Code
(Jupyter Notebook)[2.0/telephone 2.0.ipynb] handles all call-routing and 'conversation' generation. It uses OSC to send frequency and amplitude CV to [(telephone.maxpat)[2.0/telephone.maxpat], which synthesizes the 8 different 'voices'. 

Call-routing logic is implemented in (telephone.py)[2.0/telephone.py], which uses random number-based probabilities to decide who to call, how long to wait for pickup, whether to pickup, whether to redial, how long to talk for, etc. 
