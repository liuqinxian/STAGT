import os
import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def transform(data: torch.Tensor, train: bool, opt: object, start: int) -> torch.Tensor:
    '''
    predict speed in 15 minutes according to speed 1 hour ago IN A DAY
    ie. x.shape = [n_his, routes] and y.shape = [n_pred, routes]
    then, concat head and tail to the data and label  
    '''
    n_his = opt.n_his
    n_pred = opt.n_pred
    n_route = opt.n_route
    day_slot = opt.day_slot
    T4N_step = opt.T4N['step']
    
    n_day = len(data) // day_slot
    n_slot = 288 * n_day

    if train:
        n_slot = day_slot - n_his - n_pred - T4N_step + 2
        x = torch.zeros(n_day * n_slot, 1, n_his, n_route)
        y = torch.zeros(n_day * n_slot, 1, n_pred + T4N_step - 1, n_route)
    else:
        n_slot = day_slot - n_his - n_pred + 1
        x = torch.zeros(n_day * n_slot, 1, n_his, n_route)
        y = torch.zeros(n_day * n_slot, 1, n_pred, n_route)

    for i in range(n_day):
        for j in range(n_slot):
            t = i * n_slot + j
            s = i * day_slot + j
            e = s + n_his
            x[t, :, :, :] = data[s : e].reshape(1, n_his, n_route)
            if train:
                length = n_pred + T4N_step - 1
                y[t, :, :, :] = data[e : e + length].reshape(1, length, n_route)
            else:
                y[t, :, :, :] = data[e : e + n_pred].reshape(1, n_pred, n_route)
            
    x = x.permute(0, 3, 2, 1)   # [slots, 1, n_his, n_route] -> [slots, n_route, n_his, 1]
    y = y.permute(0, 3, 2, 1)   # [slots, 1, n_pred, n_route] -> [slots, n_route, n_pred, 1]
    return x, y


class STGT_Dataset(torch.utils.data.Dataset):
    def __init__(self, opt: object, train: bool, val: bool) -> torch.Tensor:
        '''
        split data to Train/Val/Test dataset
        standardlize dataset
        split data 
        '''
        data = pd.read_csv(opt.data_path, header=None).values.astype(float)  # -> np.ndarray
        
        len_train = opt.n_train * opt.day_slot  # 34 * 288  288 = 24 * 12
        len_val = opt.n_val * opt.day_slot  # 5 * 288

        if train:
            start = 0
        elif val:
            start = len_train
        else:
            start = len_train + len_val

        sklearn = opt.sklearn
        if sklearn:
            scaler = opt.scaler   # standardlize dataset

        if train:
            self.dataset = data[: len_train]    # [len_train, 228]
            self.dataset = scaler.fit_transform(self.dataset)
        elif val:
            self.dataset = data[len_train : len_train + len_val]
            self.dataset = scaler.transform(self.dataset)
        else:
            self.dataset = data[len_train + len_val : len_train + len_val + len_val]
            self.dataset = scaler.transform(self.dataset)

        self.dataset = torch.Tensor(self.dataset)   # ndarray -> tensor
        self.x, self.y = transform(self.dataset, train, opt, start)
        self.x, self.y = self.x.cuda(), self.y.cuda()

    def __len__(self) -> int:
        '''
        return time slots the dataset have
        1 slot per 5 minutes
        12 slots per 1 hour
        '''
        return self.x.shape[0]    # self.dataset.shape = slots * routes = [slots, 228]

    def __getitem__(self, index: int) -> torch.Tensor:
        '''
        x || data: speed 1 hour ago
        y || label: speed 15 minutes later
        '''
        return self.x[index], self.y[index] # [1, 228, 14, 33], [1, 228, 4, 1]


