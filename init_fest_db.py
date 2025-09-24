import pickle

fest = {}
fest['JUEA-00100'] = "ENDED"
with open('fest.db','wb') as fw:

    pickle.dump(fest, fw)
