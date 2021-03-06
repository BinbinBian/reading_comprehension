import numpy as np

mask = np.asarray([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
loss_mat = np.asarray([9.90364, 9.9036217, 9.9035234, 9.9036407, 9.9036112, 9.9036226, 9.9035273, 9.9036331, 9.9035826, 9.9035244, 9.9036341, 9.9036112, 9.90363, 9.9036322, 9.9035139, 9.903513, 9.903512, 9.903513, 9.9035139, 9.90351, 9.90351, 9.90351, 9.9035091, 9.9035091, 9.9035091, 9.9035082, 9.9035082, 9.9035072, 9.9035072, 9.9035082])
masked = 138.65042

res = np.dot(mask, loss_mat)
print res
print masked
print res == masked

pred = np.zeros((1, 20000)) + (1.0/20000)
y = np.zeros((1, 20000))
y[0] = 1

diff = y - pred
sq = diff ** 2
l2 = sq / 2
print np.sum(l2)