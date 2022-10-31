import numpy as np

import tensorflow as tf
import horovod.tensorflow as hvd
    
def get_model():
    from tensorflow.keras import models
    from tensorflow.keras import layers

    model = models.Sequential()
    model.add(
        layers.Conv2D(32,
                      kernel_size=(3, 3),
                      activation='relu',
                      input_shape=(28, 28, 1)))
    model.add(layers.Conv2D(64, (3, 3), activation='relu'))
    model.add(layers.MaxPooling2D(pool_size=(2, 2)))
    model.add(layers.Dropout(0.25))
    model.add(layers.Flatten())
    model.add(layers.Dense(128, activation='relu'))
    model.add(layers.Dropout(0.5))
    model.add(layers.Dense(10, activation='softmax'))
    return model

# Initialize Horovod
hvd.init()

# Pin GPU to be used to process local rank (one GPU per process)
gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
if gpus:
    tf.config.experimental.set_visible_devices(gpus[hvd.local_rank()], 'GPU')

# Build model and dataset
(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()

x_train = (x_train / 255.0).astype(np.float32)
y_train = y_train.astype(np.float32)

x_test = (x_test / 255.0).astype(np.float32)
y_test = y_test.astype(np.float32)
dataset = tf.data.Dataset.from_tensor_slices({'inputs': x_train, 'labels': y_train})
dataset = dataset.repeat(100) \
    .shuffle(10000) \
    .batch(128) \
    .prefetch(tf.data.experimental.AUTOTUNE)

mnist_model = get_model()
loss = tf.losses.SparseCategoricalCrossentropy()
opt = tf.optimizers.Adam(0.001 * hvd.size())

checkpoint_dir = './checkpoints'
checkpoint = tf.train.Checkpoint(model=mnist_model, optimizer=opt)

@tf.function
def training_step(images, labels, first_batch):
    with tf.GradientTape() as tape:
        probs = mnist_model(images, training=True)
        loss_value = loss(labels, probs)

    # Horovod: add Horovod Distributed GradientTape.
    tape = hvd.DistributedGradientTape(tape)

    grads = tape.gradient(loss_value, mnist_model.trainable_variables)
    opt.apply_gradients(zip(grads, mnist_model.trainable_variables))

    # Note: broadcast should be done after the first gradient step to ensure optimizer
    # initialization.
    if first_batch:
        hvd.broadcast_variables(mnist_model.variables, root_rank=0)
        hvd.broadcast_variables(opt.variables(), root_rank=0)

    return loss_value

# Horovod: adjust number of steps based on number of GPUs.
for batch, data in enumerate(dataset.take(10000 // hvd.size())):
    # import pdb
    # pdb.set_trace()
    images = tf.reshape(data['inputs'],(-1,28,28,1))
    labels = data['labels']
    loss_value = training_step(images, labels, batch == 0)

    if batch % 10 == 0 and hvd.local_rank() == 0:
        print('Step #%d\tLoss: %.6f' % (batch, loss_value))

# Horovod: save checkpoints only on worker 0 to prevent other workers from
# corrupting it.
if hvd.rank() == 0:
    checkpoint.save(checkpoint_dir)