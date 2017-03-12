import time
import tensorflow as tf
import numpy as np

from embeddings_handler import EmbeddingHolder
from tf_data_handler import TFDataHolder
from embeddings_handler import EmbeddingHolder

from simple_configs import NUM_EPOCS, TRAIN_BATCH_SIZE, EMBEDDING_DIM, QUESTION_MAX_LENGTH, PASSAGE_MAX_LENGTH, INPUT_MAX_LENGTH, OUTPUT_MAX_LENGTH, MAX_NB_WORDS, LEARNING_RATE, DEPTH, HIDDEN_DIM, GLOVE_DIR, TEXT_DATA_DIR, EMBEDDING_MAT_DIR


class TFModel():
    def add_placeholders(self):
        """Generates placeholder variables to represent the input tensors
        NOTE: You do not have to do anything here.
        """
        self.question_placeholder = tf.placeholder(tf.int32, shape=(None, QUESTION_MAX_LENGTH), name="questions")
        self.passages_placeholder = tf.placeholder(tf.int32, shape=(None, PASSAGE_MAX_LENGTH), name="passages")
        self.answers_placeholder = tf.placeholder(tf.int32, shape=(None, OUTPUT_MAX_LENGTH, MAX_NB_WORDS), name="answers")

    def create_feed_dict(self, questions_batch, passages_batch, answers_batch=None):
        """Creates the feed_dict for the model.
        NOTE: You do not have to do anything here.
        """
        feed_dict = {
            self.questions_placeholder : questions_batch,
            self.passages_placeholder : passages_batch
        }
        if answers_batch is not None: feed_dict[self.answers_placeholder] = answers_batch
        return feed_dict

    def add_embedding(self, placeholder):  
        large_embeddings = tf.nn.embedding_lookup(tf.Variable(self.pretrained_embeddings), placeholder, partition_strategy='mod', name=None, validate_indices=True, max_norm=None)
        return large_embeddings
        # embeddings = tf.reshape(large_embeddings, [-1, self.config.n_features * self.config.embed_size])
        # return embeddings

    def add_prediction_op(self): 
        questions = self.add_embedding(self.questions_placeholder)
        passages = self.add_embedding(self.passages_placeholder)

        cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
        
        encoded_questions = tf.nn.bidirectional_dynamic_rnn(cell, questions, dtype=tf.float32)
        encoded_questions = tf.concat(encoded_questions[1][0], encoded_questions[1][0])
        print encoded_questions

        # Do i need an activation layer here?

        passages_entry = tf.concat(encoded_questions, passages)
        full_encodings = tf.nn.bidirectional_dynamic_rnn(cell, passages_entry, dtype=tf.float32)
        final_encodings = tf.concat(full_encodings[1][0], full_encodings[1][0])
        print final_encodings

        preds = tf.nn.sigmoid(final_encodings)

        return preds

    def add_loss_op(self, preds):
        y = self.answers_placeholder   
        loss_mat = tf.nn.softmax_cross_entropy_with_logits(preds, self.answers_placeholder)
        loss = tf.reduce_mean(loss_mat)

        return loss

    def add_training_op(self, loss):        
        train_op = tf.train.AdamOptimizer(LEARNING_RATE).minimize(loss)
        return train_op

    def train_on_batch(self, sess, questions_batch, passages_batch, answers_batch):
        """Perform one step of gradient descent on the provided batch of data."""
        feed = self.create_feed_dict(questions_batch, passages_batch, answers_batch=answers_batch)
        _, loss, _ = sess.run([self.train_op, self.loss, _], feed_dict=feed)
        return loss

    def run_epoch(self, sess, q_data, p_data, a_data):
        prog = Progbar(target=1 + int(len(train) / TRAIN_BATCH_SIZE))
        losses = []
        for i, batch in enumerate(minibatches(train, TRAIN_BATCH_SIZE)):
            loss, _ = self.train_on_batch(sess, *batch)
            losses.append(loss)
            prog.update(i + 1, [("train loss", loss)])

        return losses

    def fit(self, sess, q_data, p_data, a_data):
        losses = []
        for epoch in range(NUM_EPOCS):
            print "Epoch %d out of %d", epoch + 1, NUM_EPOCS
            loss, _ = self.run_epoch(sess, train)
            losses.append(loss)
        return losses

    def build(self):
        self.add_placeholders()
        self.pred = self.add_prediction_op()
        self.loss = self.add_loss_op(self.pred)
        self.train_op = self.add_training_op(self.loss)

    def __init__(self, embeddings):
        print embeddings
        self.pretrained_embeddings = embeddings
        self.questions_placeholder = None
        self.passages_placeholder = None
        self.answers_placeholder = None
        self.build()

if __name__ == "__main__":
    data = TFDataHolder('train')
    embeddings = EmbeddingHolder().get_embeddings_mat()
    q_data, p_data, a_data = data.get_full_data()
    with tf.Graph().as_default():
        print "Building model..."
        start = time.time()
        model = TFModel(embeddings)
        print "took %.2f seconds", time.time() - start

        init = tf.global_variables_initializer()

        with tf.Session() as session:
            session.run(init)
            losses = model.fit(session, q_data, p_data, a_data)

    print 'losses list:', losses

















