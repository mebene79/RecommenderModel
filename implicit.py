# -*- coding: utf-8 -*-
"""Implicit.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/179FgRTWwrENO6uUFvl7F0mgI_xIYGItM
"""

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import accuracy_score, mean_squared_error
from sklearn.model_selection import train_test_split
import torch.nn.init as init
import numpy as np
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
torch.cuda.manual_seed(RANDOM_SEED)
torch.backends.cudnn.deterministic = True


class Config:
    """Holds model hyperparameters and data information."""
    n_items = 733
    n_users = 1340
    n_f = 5
    lamb2 = 25
    lamb3 = 10
    lamb4 = 0.02 #0.004
    lamb5 = 0.01 #0.5
    lamb6 = 0.05
    lamb7 = 0.01
    lamb8 = 0.01
    lamb9 = 0.01 #10
    lamb10 = 0.01
    beta = 0.4
    item_bin_size = 60 #60
    n_epochs = 600 #600
    lr = 0.01 #0.005 #0000.5
    batch_size = 1024 #2048
    maxday_cat_code=4096
    global_mean_rank = 4 #4.16275031832388

class RecommendationImplicit(nn.Module, BaseEstimator, ClassifierMixin):
    def __init__(self):
        super(RecommendationImplicit, self).__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.global_mean = torch.tensor(Config.global_mean_rank, device=self.device, dtype=torch.float32)
        self.BU = nn.Parameter(torch.zeros((Config.n_users, 1), device=self.device, dtype=torch.float32))
        self.BI = nn.Parameter(torch.zeros((Config.n_items, 1), device=self.device, dtype=torch.float32))
        self.WPI = nn.Parameter(torch.zeros([Config.n_items, 5], device=self.device, dtype=torch.float32))
        #init.xavier_uniform_(self.WPI)
        self.WPU = nn.Parameter(torch.zeros([Config.n_users, 5], device=self.device, dtype=torch.float32))
        #init.xavier_uniform_(self.WPU)
        self.WBIT = nn.Parameter(torch.zeros((Config.n_items, int(Config.item_bin_size)), device=self.device, dtype=torch.float32))
        self.AlphaUK = nn.Parameter(torch.zeros((Config.n_users,5), device=self.device, dtype=torch.float))
        #init.xavier_uniform_(self.AlphaUK)
        self.WPUKT = nn.Parameter(torch.zeros((Config.maxday_cat_code+1,5), device=self.device, dtype=torch.float))
        #init.xavier_uniform_(self.WPUKT)
        self.Alpha = nn.Parameter(torch.empty((Config.n_users,1), device=self.device, dtype=torch.float))
        init.xavier_uniform_(self.Alpha)
        self.BTDay = nn.Parameter(torch.zeros(Config.maxday_cat_code+1, device=self.device, dtype=torch.float))
        self.BCU = nn.Parameter(torch.zeros([Config.n_users], device=self.device, dtype=torch.float))
        self.WCU = nn.Parameter(torch.empty((Config.maxday_cat_code+1,1), device=self.device, dtype=torch.float))
        init.xavier_uniform_(self.WCU)
        self.Y = nn.Parameter(torch.zeros((Config.n_users, 5), device=self.device, dtype=torch.float))
        #init.xavier_uniform_(self.Y)
        self.output_layer = nn.Linear(1, 5).to(self.device)  # Ensure output_layer is on the correct device
        self.optimizer = optim.Adam([self.BU, self.BI,self.WPU,self.WPI,self.WBIT,self.Alpha,self.BTDay,self.BCU,self.WCU,self.AlphaUK,self.WPUKT,self.Y, *self.output_layer.parameters()], lr=Config.lr)
        self.trained = False

    def patch_with_value(self,x, patch_value, max_length):
        new_list = np.full(max_length, patch_value, dtype=int)
        new_list[:len(x)] = x
        return new_list

    def getImplicitDF(self,X):
        max_item_id = max(X["itemID"].tolist())

        item_len_df = X.groupby("userID").agg({"itemID": lambda x: len(x)})
        item_len_df = item_len_df.reset_index(drop = True)
        user_item_df = X.groupby("userID")["itemID"].agg(itemList = lambda x:  tuple(x))
        user_item_df = user_item_df.reset_index(drop = True)
        maxlength = max(len(x) for x in user_item_df["itemList"].tolist())
        user_item_df["itemList"] = user_item_df["itemList"].apply(lambda x: self.patch_with_value(x, max_item_id + 1, maxlength))
        user_item_df["itemLen"] = item_len_df["itemID"]

        return user_item_df

    def getMeanDaybyUser(self,X):
        mean_u_day = X.groupby("userID")["ReviewDay"].agg({"mean"})
        return mean_u_day["mean"]


    def forward(self, X):
        # Ensure all operations are on the same device
        user_ids = torch.tensor(X["userID"].values.astype(int)).to(self.device)
        item_ids = torch.tensor(X["itemID"].values.astype(int)).to(self.device)
        ITBin=torch.tensor(X["ITBin"].values.astype(int)).to(self.device)
        tday=torch.tensor(X["ReviewDay"].values.astype(int)).to(self.device)
        mean_ud = torch.tensor(self.getMeanDaybyUser(X).values.astype(float), device=self.device, dtype=torch.float).reshape(-1, 1) # changed to torch.double
        maxday_cat=torch.tensor(X["TDayCat"].values.astype(int)).to(self.device)
        user_itemcount=torch.tensor(self.getImplicitDF(X)['itemLen'].values.astype(int)).to(self.device)
        user_rated_item=torch.tensor(np.array(self.getImplicitDF(X)['itemList'].values.tolist())).to(self.device)

        bias_user = self.BU[user_ids].squeeze()
        bias_item = self.BI[item_ids].squeeze()
        user_vector = self.WPU[user_ids].squeeze()
        item_vector = self.WPI[item_ids].squeeze()
        #bias_vector = torch.sum(user_factors * item_factors, dim=1)
        indices = torch.stack([torch.clamp(item_ids, 0, Config.n_items - 1), torch.clamp(ITBin, 0, Config.item_bin_size - 1).long()], dim=1)
        self.bias_item_binvalue = self.WBIT[indices[:, 0], indices[:, 1]]
        bias_item_time = bias_item + self.bias_item_binvalue
        butday=self.BTDay[maxday_cat]
        alpha_value=self.Alpha[user_ids] #.squeeze(1)
        alpha_uk_value=self.AlphaUK[user_ids]
        mean_ud_layer = nn.Embedding.from_pretrained(mean_ud)
        user_ids_clipped = torch.clamp(user_ids, 0, mean_ud_layer.num_embeddings - 1)
        mean_tday=mean_ud_layer(user_ids_clipped)
        tday_diff=tday-mean_tday.squeeze(1)
        dev_t=torch.sign(tday_diff)*torch.pow(torch.abs(tday_diff),Config.beta)
        self.bias_user_tvalue=alpha_value.squeeze(1)*dev_t
        bias_user_time=bias_user + self.bias_user_tvalue +  butday
        cu_b=self.BCU[user_ids]
        cu_t=self.WCU[maxday_cat]
        cui=cu_b+cu_t.squeeze(1)
        pkut=self.WPUKT[maxday_cat]


        y_w_extra=torch.zeros([1,5], device=self.device)
        y_w=torch.concat([self.Y,y_w_extra],dim=0)
        y_js=y_w[user_rated_item]
        y_sum=torch.sum(y_js,dim=1)
        clamped_user_ids = torch.clamp(user_ids, 0, user_rated_item.size(0) - 1)
        y_sum_el = y_sum[clamped_user_ids]
       # y_sum_el=y_sum[user_ids]

        ru_by_user = torch.pow(user_itemcount.float(), -0.5)
        clamped_user_ids = torch.clamp(user_ids, 0, ru_by_user.size(0) - 1)
        ru_list = ru_by_user[clamped_user_ids]
        #ru_list= ru_by_user[user_ids]
        #ru_list = torch.gather(ru_by_user, 0, user_itemcount)

        y_sum_el_t = y_sum_el.t()
        y_implicit_temp = y_sum_el_t * ru_list
        y_implicit = y_implicit_temp.t()
        user_vector_implicit=user_vector+y_implicit



        bias_item_time=bias_item_time*cui

        self.vector_user_tvalue = torch.transpose(torch.transpose(alpha_uk_value, 0, 1) * dev_t, 0, 1)
        user_vector_t=user_vector_implicit + self.vector_user_tvalue+pkut
        bias_vector=torch.sum(user_vector_t * item_vector, dim=1)

        pred = self.global_mean + bias_user_time + bias_item_time + bias_vector
        pred = self.output_layer(pred.unsqueeze(1))
        return pred

    def fit(self, X, y):
        self.to(self.device)  # Move the entire model to the device
        self.train()

        user_ids = torch.tensor(X["userID"].values.astype(int)).to(self.device)
        item_ids = torch.tensor(X["itemID"].values.astype(int)).to(self.device)
        ITBin=torch.tensor(X["ITBin"].values.astype(int), device=self.device, dtype=torch.long)
        ranks = torch.tensor(pd.get_dummies(y).values.argmax(axis=1)).to(self.device)
        tday=torch.tensor(X["ReviewDay"].values.astype(int), device=self.device, dtype=torch.long)
        maxday_cat=torch.tensor(X["TDayCat"].values.astype(int), device=self.device, dtype=torch.long),
        mean_ud = torch.tensor(self.getMeanDaybyUser(X).values.astype(float), device=self.device, dtype=torch.float).reshape(-1, 1) # changed to torch.double
        user_itemcount=torch.tensor(self.getImplicitDF(X)['itemLen'].values.astype(int)).to(self.device)
        user_rated_item=torch.tensor(np.array(self.getImplicitDF(X)['itemList'].values.tolist())).to(self.device)

        criterion = nn.CrossEntropyLoss()

        for epoch in range(Config.n_epochs):
            self.optimizer.zero_grad()
            pred = self.forward(X)
            loss = criterion(pred, ranks)+ 0.5 * Config.lamb4 * (torch.norm(self.BU) \
                    + torch.norm(self.BI)+ torch.norm(self.WPU) + torch.norm(self.WPI))\
                    +0.5 * Config.lamb5 * (torch.norm(self.bias_item_binvalue))\
                    +0.5 * Config.lamb6 * (torch.norm(self.bias_user_tvalue))\
                    +0.5 * Config.lamb7 * (torch.norm(self.BTDay))+\
                   0.5 * Config.lamb8 *(torch.norm(self.BCU)+torch.norm(self.WCU))+\
                   0.5 * Config.lamb9 * (torch.norm(self.AlphaUK)+torch.norm(self.WPUKT))+\
                   0.5 * Config.lamb10 * (torch.norm(self.Y))
            loss.backward()
            self.optimizer.step()

        self.trained = True

    def predict(self, X, y=None):
        if not self.trained:
            raise ValueError("Model has not been trained yet. Please call fit() first.")

        self.eval()
        user_ids = torch.tensor(X["userID"].values.astype(int)).to(self.device)
        item_ids = torch.tensor(X["itemID"].values.astype(int)).to(self.device)
        ITBin=torch.tensor(X["ITBin"].values.astype(int), device=self.device, dtype=torch.long)
        tday=torch.tensor(X["ReviewDay"].values.astype(int), device=self.device, dtype=torch.long)
        mean_ud = torch.tensor(self.getMeanDaybyUser(df).values.astype(float), device=self.device, dtype=torch.float).reshape(-1, 1) # changed to torch.double
        maxday_cat=torch.tensor(X["TDayCat"].values.astype(int), device=self.device, dtype=torch.long)
        user_itemcount=torch.tensor(self.getImplicitDF(X)['itemLen'].values.astype(int)).to(self.device)
        user_rated_item=torch.tensor(np.array(self.getImplicitDF(X)['itemList'].values.tolist())).to(self.device)

        with torch.no_grad():
            pred = self.forward(X)
            y_pred = torch.argmax(pred, dim=1).cpu().numpy()  # Move to CPU before converting to numpy

        return y_pred

    def predict_proba(self, X):
        if not self.trained:
            raise ValueError("Model has not been trained yet. Please call fit() first.")

        self.eval()
        user_ids = torch.tensor(X["userID"].values.astype(int)).to(self.device)
        item_ids = torch.tensor(X["itemID"].values.astype(int)).to(self.device)
        ITBin=torch.tensor(X["ITBin"].values.astype(int)).to(self.device)
        tday=torch.tensor(X["ReviewDay"].values.astype(int)).to(self.device)
        mean_ud = torch.tensor(self.getMeanDaybyUser(X).values.astype(float), device=self.device, dtype=torch.float).reshape(-1, 1) # changed to torch.double
        maxday_cat=torch.tensor(X["TDayCat"].values.astype(int)).to(self.device)
        user_itemcount=torch.tensor(self.getImplicitDF(X)['itemLen'].values.astype(int)).to(self.device)
        user_rated_item=torch.tensor(np.array(self.getImplicitDF(X)['itemList'].values.tolist())).to(self.device)


        with torch.no_grad():
            pred = self.forward(X)
            probabilities = torch.softmax(pred, dim=1)

        return probabilities.cpu().numpy()  # Move to CPU before converting to numpy

    def score(self, X, y):
        y_pred = self.predict(X)
        return accuracy_score(y, y_pred)

    def mse(self, X, y):
        y_pred = self.predict(X)
        return mean_squared_error(y, y_pred)
