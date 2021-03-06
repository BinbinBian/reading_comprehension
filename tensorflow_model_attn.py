import time
import tensorflow as tf
import numpy as np

from model import Model
from progbar import Progbar

from embeddings_handler import EmbeddingHolder
from data_handler import DataHolder
from embeddings_handler import EmbeddingHolder
from tf_lstm_attention_cell import LSTMAttnCell
import get_predictions

from simple_configs import LOG_FILE_DIR, SAVE_MODEL_DIR, NUM_EPOCS, TRAIN_BATCH_SIZE, EMBEDDING_DIM, QUESTION_MAX_LENGTH, PASSAGE_MAX_LENGTH, OUTPUT_MAX_LENGTH, VOCAB_SIZE, LEARNING_RATE, HIDDEN_DIM

PAD_ID = 0
STR_ID = 1
END_ID = 2
SOS_ID = 3
UNK_ID = 4

class TFModel(Model):

    def add_placeholders(self):
        """Generates placeholder variables to represent the input tensors
        NOTE: You do not have to do anything here.
        """
        self.questions_placeholder = tf.placeholder(tf.int32, shape=(None, QUESTION_MAX_LENGTH), name="questions")
        self.passages_placeholder = tf.placeholder(tf.int32, shape=(None, PASSAGE_MAX_LENGTH), name="passages")
        self.answers_placeholder = tf.placeholder(tf.int32, shape=(None, OUTPUT_MAX_LENGTH), name="answers")
        self.start_token_placeholder = tf.placeholder(tf.int32, shape=(None,), name="starter_token")
        self.dropout_placeholder = tf.placeholder(tf.float32)

    def create_feed_dict(self, questions_batch, passages_batch, start_token_batch, dropout=0.5, answers_batch=None):
        """Creates the feed_dict for the model.
        NOTE: You do not have to do anything here.
        """
        feed_dict = {
            self.questions_placeholder : questions_batch,
            self.passages_placeholder : passages_batch,
            self.start_token_placeholder : start_token_batch,
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
            attn_cell = LSTMAttnCell(HIDDEN_DIM, prev_states)
            o, final_state = tf.nn.dynamic_rnn(attn_cell, inputs, dtype=tf.float32, sequence_length=mask)
        return (o, final_state)

    def add_prediction_op(self): 
        questions = self.add_embedding(self.questions_placeholder)
        passages = self.add_embedding(self.passages_placeholder)

        # Question encoder
        with tf.variable_scope("question"): 
            q_cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
            q_outputs, _ = tf.nn.dynamic_rnn(q_cell, questions, dtype=tf.float32, sequence_length=self.seq_length(self.questions_placeholder))

        # Passage encoder
        p_outputs, _ = self.encode_w_attn(passages, self.seq_length(self.passages_placeholder), q_outputs, scope = "passage_attn")
 

        # with tf.variable_scope("passage"):
        #     p_cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
        #     p_outputs, p_state_tuple = tf.nn.dynamic_rnn(p_cell, passages, initial_state=q_state_tuple, dtype=tf.float32, sequence_length=self.seq_length(passages))

        # Attention state encoder
        with tf.variable_scope("attention"): 
            a_cell = tf.nn.rnn_cell.LSTMCell(HIDDEN_DIM)
            a_outputs, _ = tf.nn.dynamic_rnn(a_cell, p_outputs, dtype=tf.float32, sequence_length=self.seq_length(self.passages_placeholder))

        q_last = tf.slice(q_outputs, [0, QUESTION_MAX_LENGTH - 1, 0], [-1, 1, -1])
        p_last = tf.slice(p_outputs, [0, PASSAGE_MAX_LENGTH - 1, 0], [-1, 1, -1])
        a_last = tf.slice(a_outputs, [0, PASSAGE_MAX_LENGTH - 1, 0], [-1, 1, -1])
        q_p_a_hidden = tf.concat(2, [q_last, p_last, a_last]) # SHAPE: [BATCH, 1, 3*HIDDEN_DIM]
       
        preds = list()
        
        with tf.variable_scope("decoder"):
            d_cell_dim = 3*HIDDEN_DIM
            d_cell = tf.nn.rnn_cell.LSTMCell(d_cell_dim) # Make decoder cell with hidden dim
 
            # Create first-time-step input to LSTM (starter token)
            #inp = self.start_token_placeholder # STARTER TOKEN, SHAPE: [BATCH, EMBEDDING_DIM]
            inp = self.add_embedding(self.start_token_placeholder) # STARTER TOKEN, SHAPE: [BATCH, EMBEDDING_DIM]

            # make initial state for LSTM cell
            h_0 = tf.reshape(q_p_a_hidden, [-1, d_cell_dim]) # hidden state from passage and question
            c_0 = tf.reshape(tf.zeros((d_cell_dim)), [-1, d_cell_dim]) # empty memory SHAPE [BATCH, 2*HIDDEN_DIM]
            h_t = tf.nn.rnn_cell.LSTMStateTuple(c_0, h_0)
            
            # U and b for manipulating the output from LSTM to logit (LSTM output -> logit)
            U = tf.get_variable('U', shape=(d_cell_dim, VOCAB_SIZE), initializer=tf.contrib.layers.xavier_initializer(), dtype=tf.float32)
            b = tf.get_variable('b', shape=(VOCAB_SIZE, ), dtype=tf.float32)
            
            for time_step in range(OUTPUT_MAX_LENGTH):
                o_t, h_t = d_cell(inp, h_t)

                o_drop_t = tf.nn.dropout(o_t, self.dropout_placeholder)
                y_t = tf.matmul(o_drop_t, U) + b # SHAPE: [BATCH, VOCAB_SIZE]
                y_t = tf.nn.softmax(y_t)

                # if self.predicting:
                inp_index = tf.argmax(y_t, 1)
                inp = tf.nn.embedding_lookup(self.pretrained_embeddings, inp_index)
                # else: 
                #     inp = tf.slice(self.answers_placeholder, [0, time_step], [-1, 1]) 
                #     inp = tf.nn.embedding_lookup(self.pretrained_embeddings, inp)
                #     inp = tf.reshape(inp, [-1, EMBEDDING_DIM])

                preds.append(y_t)
                tf.get_variable_scope().reuse_variables()

            packed_preds = tf.pack(preds, axis=2)
            preds = tf.transpose(packed_preds, perm=[0, 2, 1])
        return preds

    def add_loss_op(self, preds):
        masks = tf.cast( tf.sequence_mask(self.seq_length(self.answers_placeholder), OUTPUT_MAX_LENGTH), tf.float32)

        # print masks
        # masks = tf.Print(masks, [masks], message="Masks:", summarize=OUTPUT_MAX_LENGTH)
        
        loss_mat = tf.nn.sparse_softmax_cross_entropy_with_logits(preds, self.answers_placeholder)

        # print loss_mat
        # loss_mat = tf.Print(loss_mat, [loss_mat], message="loss_mat:", summarize=OUTPUT_MAX_LENGTH)

        # masked_loss_mat = tf.boolean_mask(loss_mat, masks)
        masked_loss_mat = tf.multiply(loss_mat, masks)

        # print masked_loss_mat
        # masked_loss_mat = tf.Print(masked_loss_mat, [masked_loss_mat], message="masked_loss_mat:", summarize=OUTPUT_MAX_LENGTH)

        masked_loss_mat = tf.reduce_sum(masked_loss_mat, axis=1)

        # print masked_loss_mat
        # masked_loss_mat = tf.Print(masked_loss_mat, [masked_loss_mat], message="reduced masked_loss_mat:", summarize=TRAIN_BATCH_SIZE)

        loss = tf.reduce_mean(masked_loss_mat)
        tf.summary.scalar('cross_entropy_loss', loss)

        # print loss
        # loss = tf.Print(loss, [loss], message="loss:")

        return loss

    def add_training_op(self, loss):        
        # train_op = tf.train.AdamOptimizer(LEARNING_RATE).minimize(loss)
        optimizer = tf.train.AdamOptimizer(LEARNING_RATE)

        grad_var_pairs = optimizer.compute_gradients(loss)
        grads = [g[0] for g in grad_var_pairs]
        grad_norm = tf.global_norm(grads)
        tf.summary.scalar('Global Gradient Norm', grad_norm)

        return optimizer.apply_gradients(grad_var_pairs)

    def run_epoch(self, sess, merged, data):
        prog = Progbar(target=1 + int(data.data_size / TRAIN_BATCH_SIZE), file_given=self.log)
        
        losses = list()
        i = 0
        batch = data.get_selected_passage_batch()
        while batch is not None:
            q_batch = batch['question']
            p_batch = batch['passage']
            a_batch = batch['answer']
            s_t_batch = batch['start_token']
            dropout = batch['dropout']
            self._temp_test_answer_indices = a_batch

            loss = self.train_on_batch(sess, merged, q_batch, p_batch, s_t_batch, dropout, a_batch)
            tf.summary.scalar('Loss per Batch', loss)
            losses.append(loss)

            prog.update(i + 1, [("train loss", loss)])

            batch = data.get_selected_passage_batch()
            if i % 1200 == 0 and i > 0:
                self.log.write('\nNow saving file...')
                saver.save(sess, SAVE_MODEL_DIR)
                self.log.write('\nSaved...')
            i += 1
        return losses

    def predict(self, sess, saver, data):
        self.predicting = True
        prog = Progbar(target=1 + int(data.data_size / TRAIN_BATCH_SIZE), file_given=self.log)
        
        preds = list()
        i = 0
        
        data.reset_iter()
        batch = data.get_selected_passage_batch(predicting=True)
        while batch is not None:
            q_batch = batch['question']
            p_batch = batch['passage']
            s_t_batch = batch['start_token']
            a_batch = np.zeros((q_batch.shape[0], OUTPUT_MAX_LENGTH), dtype=np.int32)
            dropout = batch['dropout']

            prediction = self.predict_on_batch(sess, q_batch, p_batch, s_t_batch, dropout, a_batch)
            preds.append(prediction)

            prog.update(i + 1, [("Predictions going...", 1)])

            batch = data.get_selected_passage_batch(predicting=True)
            i += 1

        return preds

    def predict_on_batch(self, sess, questions_batch, passages_batch, start_token_batch, dropout, answers_batch):
        feed = self.create_feed_dict(questions_batch, passages_batch, start_token_batch, dropout, answers_batch)
        predictions = sess.run(tf.nn.softmax(self.pred), feed_dict=feed)
        self._temp_test_pred_softmax = predictions
        predictions = np.argmax(predictions, axis=2)
        self._temp_test_pred_argmax = predictions
        return predictions


    def debug_predictions(self):
        preds_from_training = self.last_preds
        preds_from_prediction = self._temp_test_pred_softmax
        
        sumPred = 0
        sumTrain = 0

        length = np.sum(np.sign(self._temp_test_answer_indices), axis=1)
        if len(length) > 1: length = length[0]

        for i in range(OUTPUT_MAX_LENGTH):


            one_hot_location = int(self._temp_test_answer_indices[0][i])
            
            yhat_value_train = preds_from_training[0][i][one_hot_location]
            yhat_value = preds_from_prediction[0][i][one_hot_location]

            log_yhat_value_train = -1 * np.log(yhat_value_train, dtype=np.float32)
            log_yhat_value = -1 * np.log(yhat_value, dtype=np.float32)

            print "#", i, " p y_hat: ", yhat_value, " p log y_hat : ", log_yhat_value, " t y_hat: ", yhat_value_train, " t log y_hat : ", log_yhat_value_train
            
            if i < length:
                sumPred += log_yhat_value
                sumTrain += log_yhat_value_train

        print "sumPred : ", sumPred
        print "sumTrain : ", sumTrain
        print "pred argmax ", self._temp_test_pred_argmax
        print "train argmax ", np.argmax(preds_from_training, axis = 2)

        print "answer indices ", self._temp_test_answer_indices



    def __init__(self, embeddings, predicting=False):
        self.predicting = predicting
        self.pretrained_embeddings = tf.Variable(embeddings)
        self.log = open(LOG_FILE_DIR, "a")
        self.build()

if __name__ == "__main__":
    print 'Starting, and now printing to log.txt'
    data = DataHolder('train')
    embeddings = EmbeddingHolder().get_embeddings_mat()
    with tf.Graph().as_default():
        start = time.time()
        model = TFModel(embeddings)
        model.log.write("\nBuild graph took " + str(time.time() - start) + " seconds")

        init = tf.global_variables_initializer()
        saver = tf.train.Saver()
        model.log.write('\ninitialzed variables')
        config = tf.ConfigProto()
        # config.gpu_options.allow_growth=True
        # config.gpu_options.per_process_gpu_memory_fraction = 0.6

        with tf.Session(config=config) as session:
            merged = tf.summary.merge_all()
            session.run(init)
            model.log.write('\nran init, fitting.....')
            losses = model.fit(session, saver, merged, data)

            model.log.write("starting predictions now.....")
            preds = model.predict(session, saver, data)
            index_word = get_predictions.get_index_word_dict()
            preds = get_predictions.sub_in_word(preds, index_word)
            print 'Predictions:', preds
            get_predictions.build_json_file(preds, './data/train_preds.json')

    model.debug_predictions();
    model.train_writer.close()
    model.test_writer.close()
    model.log.close()
















