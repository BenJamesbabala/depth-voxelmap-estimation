import tensorflow as tf
from tensorflow.python.platform import gfile
import numpy as np
from PIL import Image

IMAGE_HEIGHT = 240
IMAGE_WIDTH = 320
TARGET_HEIGHT = 120
TARGET_WIDTH = 160

DEPTH_DIM = 200

D_MIN = 0.5
D_MAX = 50
Q = (np.log(D_MAX) - np.log(D_MIN)) / (DEPTH_DIM - 1)

MIN_DEQUE_EXAMPLES = 500  # should be relatively big compared to dataset, see https://stackoverflow.com/questions/43028683/whats-going-on-in-tf-train-shuffle-batch-and-tf-train-batch


class DataSet:
    def __init__(self, batch_size):
        self.batch_size = batch_size

    def load_params(self, train_file_path):
        filenames = np.recfromcsv(train_file_path, delimiter=',', dtype=None)
        depths = np.zeros((TARGET_HEIGHT, TARGET_WIDTH, len(filenames)))
        for i, (rgb_name, depth_name) in enumerate(filenames):
            img = Image.open(depth_name)
            img.load()
            img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.ANTIALIAS)
            data = np.asarray(img, dtype="int32")
            depths[:, :, i] = data

    def csv_inputs(self, csv_file_path):
        filename_queue = tf.train.string_input_producer([csv_file_path], shuffle=True)
        reader = tf.TextLineReader()
        _, serialized_example = reader.read(filename_queue)
        filename, depth_filename = tf.decode_csv(serialized_example, [["path"], ["annotation"]])
        # input
        jpg = tf.read_file(filename)
        image = tf.image.decode_jpeg(jpg, channels=3)
        image = tf.cast(image, tf.float32)
        # target
        depth_png = tf.read_file(depth_filename)
        depth = tf.image.decode_png(depth_png, channels=1)
        depth = tf.cast(depth, tf.float32)
        depth = tf.div(depth, [255.0])
        # depth = tf.cast(depth, tf.int64)
        # resize
        image = tf.image.resize_images(image, (IMAGE_HEIGHT, IMAGE_WIDTH))
        depth = tf.image.resize_images(depth, (TARGET_HEIGHT, TARGET_WIDTH))
        depth_bins = self.discretize_depth(depth)

        invalid_depth = tf.sign(depth)
        # generate batch
        images, depths, depth_bins, invalid_depths = tf.train.shuffle_batch(
            [image, depth, depth_bins, invalid_depth],
            batch_size=self.batch_size,
            num_threads=4,
            capacity=MIN_DEQUE_EXAMPLES + 5 * self.batch_size,
            min_after_dequeue=MIN_DEQUE_EXAMPLES)
        return images, depths, depth_bins, invalid_depths

    def discretize_depth(self, depth):
        d_min = tf.constant(D_MIN, dtype=tf.float32)
        q = tf.constant(Q, dtype=tf.float32)
        ones_vec = tf.ones((TARGET_HEIGHT, TARGET_WIDTH, DEPTH_DIM + 1))
        sth = tf.expand_dims(tf.constant(np.append(np.array(range(DEPTH_DIM)), np.inf)), 0)
        sth = tf.expand_dims(sth, 0)
        indices_vec = tf.tile(sth, [TARGET_HEIGHT, TARGET_WIDTH, 1])
        indices_vec_lower = indices_vec - 1
        # indices = ones_vec * indices_vec
        # indices = ones_vec * indices_vec
        # bin value = bin_idx * q + log(d_min)
        d_min_tensor = ones_vec * tf.log(d_min)
        bin_value = q * tf.cast(indices_vec, tf.float32)
        bin_value_lower = q * tf.cast(indices_vec_lower, tf.float32)
        logged = d_min_tensor + bin_value
        logged_lower = d_min_tensor + bin_value_lower
        mask = tf.exp(logged)  # values corresponding to this bin, for comparison
        mask_lower = tf.exp(logged_lower)  # values corresponding to this bin, for comparison
        depth_discretized = tf.cast(tf.less_equal(depth, mask), tf.int8) * tf.cast(tf.greater(depth, mask_lower),
                                                                                   tf.int8)
        return depth_discretized

    def discretized_to_depth(self, depth_bins):
        weights = np.array(range(DEPTH_DIM)) * Q + np.log(D_MIN)
        mask = np.tile(weights, (TARGET_HEIGHT, TARGET_WIDTH, 1))
        depth = np.exp(np.sum(np.multiply(mask, depth_bins), axis=2))
        return depth

    def output_predict(self, depths, images, output_dir):
        print("output predict into %s" % output_dir)
        if not gfile.Exists(output_dir):
            gfile.MakeDirs(output_dir)
        for i, (image, depth) in enumerate(zip(images, depths)):
            pilimg = Image.fromarray(np.uint8(image))
            image_name = "%s/%05d_org.png" % (output_dir, i)
            pilimg.save(image_name)
            # depth = depth.transpose(2, 0, 1)
            # depth = self.discretized_to_depth(depth)
            if np.max(depth) != 0:
                ra_depth = (depth / np.max(depth)) * 255.0
            else:
                ra_depth = depth * 255.0
            depth_pil = Image.fromarray(np.uint8(ra_depth), mode="L")
            depth_name = "%s/%05d.png" % (output_dir, i)
            depth_pil.save(depth_name)
