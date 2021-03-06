import os
import numpy as np
import cPickle
import h5py

from sklearn.preprocessing import OneHotEncoder
from simple_configs import LOG_FILE_DIR, TRAIN_BATCH_SIZE, EMBEDDING_DIM, OUTPUT_MAX_LENGTH, VOCAB_SIZE, QUESTION_MAX_LENGTH, PASSAGE_MAX_LENGTH, MAX_DATA_SIZE

PAD_ID = 0
END_ID = 1
UNK_ID = 2
STR_ID = 3
SOS_ID = 4

PAD_ID = 0
END_ID = 1
UNK_ID = 2
STR_ID = 3
SOS_ID = 4

class TFDataHolder:

	# pass in data_set ('train', 'val', 'dev')
	def __init__(self, DATA_SET, batch_size=TRAIN_BATCH_SIZE):
		self.log = open(LOG_FILE_DIR, "a")
		self.log.write('\n\n\n\ninitializing tf Data Holder')
		self.data_set = str(DATA_SET).lower()
		DATA_FILE = './data/marco/h5py-' +  self.data_set

		if not os.path.isfile(DATA_FILE):
			h5f = h5py.File(DATA_FILE, 'w')
			h5f.create_dataset('q_data', data=self.build_Q_data())			
			h5f.create_dataset('p_data', data=self.build_P_data())			
			h5f.create_dataset('a_data', data=self.build_A_data())
			h5f.close()

		h5f = h5py.File(DATA_FILE,'r')
		self.Q_data = h5f['q_data']
		self.P_data = h5f['p_data']
		self.A_data = h5f['a_data']
		self.data_size = self.Q_data.shape[0] if MAX_DATA_SIZE == -1 else MAX_DATA_SIZE

		self.start_token = self.build_start_token(batch_size)

		self.start_iter = 0


	# This constructs the data from the pickled objects
	def build_Q_data(self):
		questions_list = cPickle.load(open("./data/marco/" + self.data_set + ".ids.question.pkl","rb"))
		self.data_size = len(questions_list)
		Q_data = np.zeros((self.data_size, QUESTION_MAX_LENGTH))
		for i, question in enumerate(questions_list):

			# padding
			if len(question) < QUESTION_MAX_LENGTH:
				pad = [PAD_ID] * (QUESTION_MAX_LENGTH - len(question))
				question.extend(pad)

			Q_data[i] = np.array(question[:QUESTION_MAX_LENGTH])
		Q_data = np.where(Q_data < MAX_NB_WORDS, Q_data, UNK_ID)
<<<<<<< HEAD
=======

>>>>>>> 6e08c851360684a3b9830fc46bac6e27f65b3f85
		np.save("./data/marco/" + self.data_set + ".data.q_data", Q_data)

		self.log.write('\nbuilt q data')
		return Q_data

	# This constructs the data from the pickled objects
	def build_P_data(self):
		passages_list = cPickle.load(open("./data/marco/" + self.data_set + ".ids.passage.pkl","rb"))
		P_data = np.zeros((self.data_size, PASSAGE_MAX_LENGTH))
		for i, p_l in enumerate(passages_list):
			for passage_tuple in p_l:
				#is_selected, passage = passage_tuple
				passage = passage_tuple
				
				# padding
				if len(passage) < PASSAGE_MAX_LENGTH:
					passage.extend([PAD_ID] * (PASSAGE_MAX_LENGTH - len(passage)) )

				P_data[i] = np.array(passage[:PASSAGE_MAX_LENGTH])
<<<<<<< HEAD
		P_data = np.where(P_data < MAX_NB_WORDS, P_data, UNK_ID)
=======

		P_data = np.where(P_data < MAX_NB_WORDS, P_data, UNK_ID)
  
>>>>>>> 6e08c851360684a3b9830fc46bac6e27f65b3f85
		np.save("./data/marco/" + self.data_set + ".data.p_data", P_data)

		self.log.write('\nbuilt p data')
		return P_data


	def build_A_data(self):
		answers_list = cPickle.load(open("./data/marco/" + self.data_set + ".ids.answer.pkl","rb" ))
		A_data = np.zeros((self.data_size, OUTPUT_MAX_LENGTH))
		for i, ans in enumerate(answers_list):
			# simply take the first answer if there are multiple answers
			ans = ans[0] if len(ans) >= 1 else []
			# pad / truncate values
			pad_len = OUTPUT_MAX_LENGTH - len(ans) - 1
			if len(ans) < OUTPUT_MAX_LENGTH: ans.extend( [END_ID] + [PAD_ID] * pad_len )
			# add to matrix
			A_data[i] = np.array(ans[:OUTPUT_MAX_LENGTH])
      
		A_data = np.where(A_data < MAX_NB_WORDS, A_data, UNK_ID)

<<<<<<< HEAD
		A_data = np.where(A_data < MAX_NB_WORDS, A_data, UNK_ID)
=======
>>>>>>> 6e08c851360684a3b9830fc46bac6e27f65b3f85
		np.save("./data/marco/" + self.data_set + ".data.a_data", A_data)

		self.log.write('\nbuilt y data')
		return A_data


	def build_start_token(self, batch_size=TRAIN_BATCH_SIZE):
		token_mat = np.zeros((batch_size, EMBEDDING_DIM))
		for row in token_mat:
			row[1] = 1
		return token_mat

	def get_full_data(self):
		self.log.write('\nbuilding full Y data')
		return self.Q_data, self.P_data, self.A_data, self.start_token

	def get_batch(self, batch_size=TRAIN_BATCH_SIZE):
		if self.start_iter >= self.data_size:
			self.start_iter = 0
			return None
		end = min(self.data_size, self.start_iter + batch_size)
		batch_size = end - self.start_iter
		to_return = (
				self.Q_data[0:batch_size], #[self.start_iter:end], 
				self.P_data[0:batch_size], #[self.start_iter:end], 
				self.A_data[0:batch_size], #[self.start_iter:end], 
				self.start_token[:batch_size]
				)
		self.start_iter += batch_size
		return to_return

if __name__ == "__main__":
	data_module = TFDataHolder('train')
	print 'Lets check out data set'
	print 'Length of Q_data: ', data_module.Q_data.shape
	print 'Length of P_data ', data_module.P_data.shape
	print 'Length of A_data ', data_module.A_data.shape
	print 'Length of Start Token ', data_module.start_token.shape
	print 'Data Size ', data_module.data_size

	print 'Making batch'
	batch = data_module.get_batch()
	print 'Batch Q ', batch[0].shape
	print 'Batch P ', batch[1].shape
	print 'Batch A ', batch[2].shape
	print 'Batch ST ', batch[3].shape














