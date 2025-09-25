#region imports
from AlgorithmImports import *
#endregion
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import argrelextrema
from collections import deque
from matplotlib.lines import Line2D
from datetime import timedelta

'''
    Much of this code is sourced at the following link: https://raposa.trade/blog/higher-highs-lower-lows-and-calculating-price-trends-in-python/
'''

def getHigherLows(data: np.array, order, K):
  '''
  Finds consecutive higher lows in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive lows need to be higher.
  '''
  # Get lows
  low_idx = argrelextrema(data, np.less, order=order)[0]
  lows = data[low_idx]
  # Ensure consecutive lows are higher than previous lows
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(low_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if lows[i] < lows[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def getLowerHighs(data: np.array, order=5, K=2):
  '''
  Finds consecutive lower highs in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive highs need to be lower.
  '''
  # Get highs
  high_idx = argrelextrema(data, np.greater, order=order)[0]
  highs = data[high_idx]
  # Ensure consecutive highs are lower than previous highs
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(high_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if highs[i] > highs[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def getHigherHighs(data: np.array, order, K):
  '''
  Finds consecutive higher highs in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive highs need to be higher.
  '''
  # Get highs
  high_idx = argrelextrema(data, np.greater, order = order)[0]
  highs = data[high_idx]
  # Ensure consecutive highs are higher than previous highs
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(high_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if highs[i] < highs[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def getLowerLows(data: np.array, order, K):
  '''
  Finds consecutive lower lows in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive lows need to be lower.
  '''
  # Get lows
  low_idx = argrelextrema(data, np.less, order=order)[0]
  lows = data[low_idx]
  # Ensure consecutive lows are lower than previous lows
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(low_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if lows[i] > lows[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def get_trend(close_data, order, K):
    '''
    Get the trend of the stock
    '''

    close_data = [x for x in close_data]
    close_data.reverse()

    # data set to dataframe empty
    data = pd.DataFrame()
    data['Close'] = close_data
    close = data['Close'].values

    hh = getHigherHighs(close, order, K)
    hl = getHigherLows(close, order, K)
    ll = getLowerLows(close, order, K)
    lh = getLowerHighs(close, order, K)


    # format for tuples inside patterns: [type, location first price, location second price, first price, second price]
    patterns = []
    for pattern in hh:
    # append a tuple with date and "hh"
        patterns.append(('hh', pattern[0], pattern[1], close[pattern[0]], close[pattern[1]]))
    for pattern in hl:
        patterns.append(('hl', pattern[0], pattern[1], close[pattern[0]], close[pattern[1]]))
    for pattern in ll:
        patterns.append(('ll', pattern[0], pattern[1], close[pattern[0]], close[pattern[1]]))
    for pattern in lh:
        patterns.append(('lh', pattern[0], pattern[1], close[pattern[0]], close[pattern[1]]))

    # sort by the second date
    patterns.sort(key=lambda x: x[2], reverse=True)

    trend = 0

    total_movements = patterns
    total_swing_up = 0
    total_swing_down = 0
    for x in total_movements:
        if x[0] == 'hh' or x[0] == 'hl':
            total_swing_up += (x[4] - x[3])
        else:
            total_swing_down += (x[4] - x[3])
    
    total_swing = total_swing_up + total_swing_down

    return total_swing
                           


