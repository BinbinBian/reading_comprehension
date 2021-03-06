import time
import tensorflow as tf
import numpy as np

from model import Model
from progbar import Progbar

from embeddings_handler import EmbeddingHolder
from data_handler import DataHolder
from embeddings_handler import EmbeddingHolder
from tf_lstm_attention_cell import LSTMAttnCell
from passage_classifier_eval import classifier_eval

from simple_configs import LOG_FILE_DIR, SAVE_MODEL_DIR, NUM_EPOCS, TRAIN_BATCH_SIZE, EMBEDDING_DIM, QUESTION_MAX_LENGTH, PASSAGE_MAX_LENGTH, OUTPUT_MAX_LENGTH, VOCAB_SIZE, LEARNING_RATE, HIDDEN_DIM, MAX_NUM_PASSAGES, ACTIVATION_FUNC, MAX_GRAD_NORM

PAD_ID = 0
STR_ID = 1
END_ID = 2
SOS_ID = 3
UNK_ID = 4

class PassClassifier(Model):
	def add_placeholders(self):
		"""Generates placeholder variables to represent the input tensors
		NOTE: You do not have to do anything here.
		"""
		self.questions_placeholder = tf.placeholder(tf.int32, shape=(None, QUESTION_MAX_LENGTH), name="questions")
		self.passages_placeholder = tf.placeholder(tf.int32, shape=(None, MAX_NUM_PASSAGES, PASSAGE_MAX_LENGTH), name="passages")
		self.answers_placeholder = tf.placeholder(tf.int32, shape=(None, ), name="answers")
		self.dropout_placeholder = tf.placeholder(tf.float32)

	def create_feed_dict(self, questions_batch, passages_batch, dropout=0.5, answers_batch=None):
		"""Creates the feed_dict for the model.
		NOTE: You do not have to do anything here.
		"""
		feed_dict = {
			self.questions_placeholder : questions_batch,
			self.passages_placeholder : passages_batch,
			self.dropout_placeholder : dropout
		}
		if answers_batch is not None: feed_dict[self.answers_placeholder] = answers_batch
		return feed_dict

	def add_embedding(self, placeholder):  
		embeddings = tf.nn.embedding_lookup(self.pretrained_embeddings, placeholder)
		return embeddings

	def seq_length(self, sequence):
		# used = tf.sign(tf.reduce_max(tf.abs(sequence), reduction_indices=2))
		used = tf.sign(sequence)
		length = tf.reduce_sum(used, reduction_indices=1)
		length = tf.cast(length, tf.int32)
		return length

	def encode_w_attn(self, inputs, mask, prev_states, scope="", reuse=False):
		
		with tf.variable_scope(scope, reuse):
			attn_cell = LSTMAttnCell(HIDDEN_DIM, prev_states, HIDDEN_DIM)
			o, final_state = tf.nn.dynamic_rnn(attn_cell, inputs, dtype=tf.float32, sequence_length=mask)
		return (o, final_state)

	def add_prediction_op(self): 
		questions = self.add_embedding(self.questions_placeholder)
		passages = self.add_embedding(self.passages_placeholder)

		# Question encoder
		with tf.variable_scope("question"): 
			q_cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
			q_outputs, q_final_tuple = tf.nn.dynamic_rnn(q_cell, questions, dtype=tf.float32, sequence_length=self.seq_length(self.questions_placeholder))
			q_final_c, q_final_h = q_final_tuple
			q_final_h = tf.expand_dims(q_final_h, axis=1)

		# Passage encoder
		# make list of hidden states for each of the passages in max_num_passages
		passage_list = list()
		for i in range(MAX_NUM_PASSAGES):

			# get mask for current passage
			curr_passage_ids = tf.slice(self.passages_placeholder, [0, i, 0], [-1, 1, -1])
			curr_passage_ids = tf.reshape(curr_passage_ids, [-1, PASSAGE_MAX_LENGTH])

			# get data for current passage
			curr_passage_embeds = tf.slice(passages, [0, i, 0, 0], [-1, 1, -1, -1])
			curr_passage_embeds = tf.reshape(curr_passage_embeds, [-1, PASSAGE_MAX_LENGTH, EMBEDDING_DIM])

			# encode passage
			p_outputs, p_final_tuple = self.encode_w_attn(curr_passage_embeds, self.seq_length(curr_passage_ids), q_outputs, scope = "passage_attn_"+str(i))
			p_final_c, p_final_h = p_final_tuple
			p_final_h = tf.expand_dims(p_final_h, axis=1)

			# encode passage again with attention
			with tf.variable_scope("attention" + str(i)): 
				a_cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
				a_outputs, a_final_tuple = tf.nn.dynamic_rnn(a_cell, p_outputs, dtype=tf.float32, sequence_length=self.seq_length(curr_passage_ids))
				a_final_c, a_final_h = a_final_tuple
				a_final_h = tf.expand_dims(a_final_h, axis=1)

			# "decode" by getting score on the passage
			encoded_dim = 3 * HIDDEN_DIM # 10 a_final_h's 10 p_final_hs and 1 q_final_h           
			encoded_mat = tf.concat(2, [q_final_h, p_final_h, a_final_h])
			encoded_mat = tf.reshape(encoded_mat, [-1, encoded_dim])

			with tf.variable_scope("scores" + str(i)):
				W = tf.get_variable('score_W', shape=(encoded_dim, HIDDEN_DIM), initializer=tf.contrib.layers.xavier_initializer(), dtype=tf.float32)
				b1 = tf.get_variable('score_b1', shape=(HIDDEN_DIM, ), dtype=tf.float32)
				U = tf.get_variable('score_U', shape=(HIDDEN_DIM, 1), initializer=tf.contrib.layers.xavier_initializer(), dtype=tf.float32)

				h = tf.nn.relu(tf.matmul(encoded_mat, W) + b1) # SHAPE: [BATCH, MAX_NUM_PASSAGE]
				scores = tf.matmul(h, U)

				passage_list.append(scores)

		scores_mat = tf.reshape(tf.pack(passage_list, axis=1), [-1, MAX_NUM_PASSAGES])
		return scores_mat


	def add_loss_op(self, preds):
		loss_vec = tf.nn.sparse_softmax_cross_entropy_with_logits(preds, self.answers_placeholder)
		loss = tf.reduce_mean(loss_vec)
		tf.summary.scalar('Classifier Loss per Batch', loss)
		return loss

	def add_training_op(self, loss):        
		optimizer = tf.train.AdamOptimizer(LEARNING_RATE)
		tf.summary.scalar('Classifier LEARNING_RATE', loss)

		grad_var_pairs = optimizer.compute_gradients(loss)
		grads = [g[0] for g in grad_var_pairs]

		clipped_grads, _ = tf.clip_by_global_norm(grads, MAX_GRAD_NORM)
		grad_var_pairs = [(g, grad_var_pairs[i][1]) for i, g in enumerate(clipped_grads)]
		
		grad_norm = tf.global_norm(clipped_grads)
		tf.summary.scalar('Classifier Global Gradient Norm', grad_norm)

		return optimizer.apply_gradients(grad_var_pairs)

	def train_on_batch(self, sess, merged, questions_batch, passages_batch, dropout, answers_batch):
		"""Perform one step of gradient descent on the provided batch of data."""
		feed = self.create_feed_dict(questions_batch, passages_batch, dropout, answers_batch=answers_batch)
		summary, _, loss = sess.run([merged, self.train_op, self.loss], feed_dict=feed)
		self.train_writer.add_summary(summary, self.step)
		self.step += 1
		return loss

	def fit(self, sess, saver, merged, data):
		losses = []
		for epoch in range(NUM_EPOCS):
			self.log.write("\nEpoch: " + str(epoch + 1) + " out of " + str(NUM_EPOCS))
			loss = self.run_epoch(sess, merged, data)
			losses.append(loss)
			acc = self.predict_now(sess, str(epoch))
			if acc >= self.best_accuracy:
				saver.save(sess, SAVE_MODEL_DIR)
				self.best_accuracy = acc
		return losses

	def predict_now(self, session, identifier):
		preds = self.predict(session, self.val_data)
		list_preds = list()
		for batch in preds:
			for row in batch:
				list_preds.append(row)
		preds = np.asarray(list_preds)
		y = self.val_data.get_full_selected()
		acc, recall, prec, f1 = classifier_eval(preds, y, self.log)
		return acc

	def run_epoch(self, sess, merged, data):
		prog = Progbar(target=1 + int(data.data_size / TRAIN_BATCH_SIZE), file_given=self.log)
		
		losses = list()
		i = 0
		batch = data.get_batch()
		while batch is not None:
			q_batch = batch['question']
			p_batch = batch['passage']
			a_batch = batch['selected_passage']
			dropout = batch['dropout']

			loss = self.train_on_batch(sess, merged, q_batch, p_batch, dropout, a_batch)
			losses.append(loss)

			prog.update(i + 1, [("train loss", loss)])

			batch = data.get_batch()
			i += 1

		return losses

	def predict(self, sess, data):
		self.testing = False
		prog = Progbar(target=1 + int(data.data_size / TRAIN_BATCH_SIZE), file_given=self.log)
		
		preds = list()
		i = 0
		
		batch = data.get_batch(predicting=True)
		while batch is not None:
			q_batch = batch['question']
			p_batch = batch['passage']
			dropout = batch['dropout']

			prediction = self.predict_on_batch(sess, q_batch, p_batch, dropout)
			preds.append(prediction)

			prog.update(i + 1, [("Predictions going...", 1)])

			batch = data.get_batch(predicting=True)
			i += 1

		return preds

	def predict_on_batch(self, sess, questions_batch, passages_batch, dropout):
		feed = self.create_feed_dict(questions_batch, passages_batch, dropout)
		predictions = sess.run(tf.nn.softmax(self.pred), feed_dict=feed)
		predictions = np.argmax(predictions, axis=1)
		return predictions

	def __init__(self, embeddings, predicting=False):
		self.predicting = predicting
		self.pretrained_embeddings = tf.Variable(embeddings)
		self.log = open(LOG_FILE_DIR, "a")
		self.best_accuracy = float('-inf')
		self.build()

if __name__ == "__main__":
	print 'Starting Classifier, and now printing to log.txt'
	data = DataHolder('train')
	embeddings = EmbeddingHolder().get_embeddings_mat()
	with tf.Graph().as_default():
		start = time.time()
		model = PassClassifier(embeddings)
		model.log.write("\nBuild Classifier graph took " + str(time.time() - start) + " seconds")

		init = tf.global_variables_initializer()
		saver = tf.train.Saver()
		model.log.write('\ninitialzed classifier variables')
		config = tf.ConfigProto()
		with tf.Session(config=config) as session:
			merged = tf.summary.merge_all()
			session.run(init)
			model.log.write('\nran init, fitting classifier.....')
			losses = model.fit(session, saver, merged, data)

	model.log.close()
















