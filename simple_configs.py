# DATA PARAMETERS
NUM_EPOCS = 1
LEARNING_RATE = 0.001
DROPOUT = 0.8
SMALL_DATA_SET = True
MAX_DATA_SIZE = 16 #-1 to set no limit on data size
TRAIN_BATCH_SIZE = 16
MAX_GRAD_NORM = 40

# Text params
QUESTION_MAX_LENGTH = 50
PASSAGE_MAX_LENGTH = 100
OUTPUT_MAX_LENGTH = 30
MAX_NUM_PASSAGES = 10
NUM_POPULAR_WORDS = 200

# Embedding params
VOCAB_SIZE = 20000#228999 #MAX VALUE
EMBEDDING_DIM = 300

# model params
HIDDEN_DIM = 5
ACTIVATION_FUNC = 'tf.nn.relu'

# directories
GLOVE_DIR = './download/dwr/'
TEXT_DATA_DIR = './data/marco/vocab.dat'
EMBEDDING_MAT_DIR = './data/marco/embeddings' + str(EMBEDDING_DIM) + '.npy'
LOG_FILE_DIR = './log.txt'

# Save information
SAVE_PREDICTIONS_FREQUENCY = 10
SAVE_MODEL_DIR = './data/model.weights'
