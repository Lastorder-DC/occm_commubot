import pickle

fest = {}
with open('fest.db','wb') as fw:
    pickle.dump(fest, fw)