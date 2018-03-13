import tensorflow as tf
import numpy as np
from PIL import Image
import dataset
import metrics_np
from prettytable import PrettyTable
import os
import Network


def load_model_with_structure(model_name, graph, sess):
    import re
    tf.logging.info(" [*] Loading last checkpoint")

    checkpoint_dir = os.path.join('checkpoint', model_name)
    checkpoint = tf.train.get_checkpoint_state(checkpoint_dir)
    if not checkpoint or not checkpoint.model_checkpoint_path:
        print(" [*] Failed to find a checkpoint")
        return False, 0, None
    checkpoint_name = os.path.basename(checkpoint.model_checkpoint_path)
    data_file = os.path.join(checkpoint_dir, checkpoint_name)
    meta_file = data_file + '.meta'
    saver = tf.train.import_meta_graph(meta_file)
    saver.restore(sess, data_file)
    counter = int(next(re.finditer("(\d+)(?!.*\d)", checkpoint_name)).group(0))
    last_layer = graph.get_tensor_by_name('network/softmaxFinal/Reshape_1:0')
    input = graph.get_tensor_by_name('network/x:0')
    print(" [*] Success to read {} in iteration {}".format(checkpoint_name, counter))
    return True, input, last_layer


def inference(model, input, rgb_image, graph, sess):
    image_val = sess.run(model, feed_dict={
        input: rgb_image
    })
    return image_val


def evaluate_model(model_name, needs_conversion, rgb_img, truth_img):
    # not running on any GPU, using only CPU
    config = tf.ConfigProto(
        device_count={'GPU': 0}
    )
    with tf.Graph().as_default() as graph:
        with tf.Session(config=config) as sess:
            _, input, model = load_model_with_structure(model_name, graph, sess)
            if needs_conversion:
                model = Network.Network.bins_to_depth(model)
            pred_img = inference(model, input, rgb_img, graph, sess)

    return {
        'treshold_1.25': metrics_np.accuracy_under_treshold(truth_img, pred_img, 1.25),
        'mean_rel_err': metrics_np.mean_relative_error(truth_img, pred_img),
        'rms': metrics_np.root_mean_squared_error(truth_img, pred_img),
        'rms_log': metrics_np.root_mean_squared_log_error(truth_img, pred_img),
        'log10_err': metrics_np.log10_error(truth_img, pred_img),
    }


def get_evaluation_names():
    return {
        'treshold_1.25',
        'mean_rel_err',
        'rms',
        'rms_log',
        'log10_err',
    }


if __name__ == '__main__':
    model_names = [
        # format is name, needs conversion from bins
        ['2018-03-11--23-23-32', True],
        ['2018-03-11--15-30-10', True],
        ['2018-03-11--14-40-26', True],
    ]

    images = [
        ['data/nyu_datasets/00836.jpg', 'data/nyu_datasets/00836.png'],
    ]

    batch_rgb = np.zeros((len(images), dataset.IMAGE_HEIGHT, dataset.IMAGE_WIDTH, 3))
    batch_depth = np.zeros((len(images), dataset.TARGET_HEIGHT, dataset.TARGET_WIDTH, 1))
    for i, (rgb_name, depth_name) in enumerate(images):
        rgb_img = Image.open(rgb_name)
        rgb_img = rgb_img.resize((dataset.IMAGE_WIDTH, dataset.IMAGE_HEIGHT), Image.ANTIALIAS)
        image_rgb = np.asarray(rgb_img, dtype="int32")
        batch_rgb[i, :, :, :] = image_rgb

        depth_img = Image.open(depth_name)
        depth_img = depth_img.resize((dataset.TARGET_WIDTH, dataset.TARGET_HEIGHT), Image.ANTIALIAS)
        image_depth = np.asarray(depth_img, dtype="int32")
        batch_depth[i, :, :, 0] = image_depth
    Network.BATCH_SIZE = len(images)


    x = PrettyTable(get_evaluation_names())
    for model_name, needs_conv in model_names:
        accuracies = evaluate_model(model_name, needs_conv, batch_rgb, batch_depth)
        x.add_row(accuracies)

    print(x)
