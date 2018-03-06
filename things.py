import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image


def output_predict(depths, images, depths_discretized, output_dir):
    print("output predict into %s" % output_dir)
    if not tf.gfile.Exists(output_dir):
        tf.gfile.MakeDirs(output_dir)
    for i, _ in enumerate(images):
        image, depth, depth_discretized = images[i], depths[i], depths_discretized[i]

        pilimg = Image.fromarray(np.uint8(image))
        image_name = "%s/%03d_org.png" % (output_dir, i)
        pilimg.save(image_name)
        depth = depth.transpose(2, 0, 1)
        if np.max(depth) != 0:
            ra_depth = (depth / np.max(depth)) * 255.0
        else:
            ra_depth = depth * 255.0
        depth_pil = Image.fromarray(np.uint8(ra_depth[0]), mode="L")
        depth_name = "%s/%03d.png" % (output_dir, i)
        depth_pil.save(depth_name)

        for j in range(DEPTH_DIM):
            ra_depth = depth_discretized[:, :, j] * 255.0
            depth_discr_pil = Image.fromarray(np.uint8(ra_depth), mode="L")
            depth_discr_name = "%s/%03d_%03d_discr.png" % (output_dir, i, j)
            depth_discr_pil.save(depth_discr_name)


if __name__ == '__main__':
    d = list(range(1, 100))
    d_min = np.min(d)
    d_max = 20
    num_bins = 10
    q_calc = (np.log(np.max(d)) - np.log(d_min)) / (num_bins - 1)
    # q = 0.5  # width of quantization bin
    l = np.round((np.log(d) - np.log(d_min)) / q_calc)

    print(d)
    print(l)

    print(q_calc)
    #
    # f, axarr = plt.subplots(2, 2)
    # axarr[0, 0].plot(d)
    # axarr[0, 1].plot(np.log(d))
    # axarr[1, 0].plot(np.log(d) - np.log(d_min))
    # axarr[1, 1].plot((np.log(d) - np.log(d_min)) / q_calc)
    # plt.show()

    with tf.Graph().as_default():
        with tf.Session() as sess:
            x = tf.constant(d)
            mask = tf.constant([])

    # for i in range(500):
    #     if i % 500 == 0:
    #         print('hi', i)

            IMAGE_HEIGHT = 240
            IMAGE_WIDTH = 320
            TARGET_HEIGHT = 120
            TARGET_WIDTH = 160
            DEPTH_DIM = 10

            filename_queue = tf.train.string_input_producer(['train.csv'], shuffle=True)
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

            d_min = tf.reduce_min(depth)
            d_max = tf.reduce_max(depth)
            q = (tf.log(d_max) - tf.log(d_min)) / (DEPTH_DIM - 1)
            bin_idx = tf.round((tf.log(depth) - tf.log(d_min)) / q)
            ones_vec = tf.ones((TARGET_HEIGHT, TARGET_WIDTH, DEPTH_DIM))
            sth = tf.expand_dims(tf.constant(np.array(range(DEPTH_DIM))), 0)
            sth = tf.expand_dims(sth, 0)
            indices_vec = tf.tile(sth, [TARGET_HEIGHT, TARGET_WIDTH, 1])
            # indices = ones_vec * indices_vec
            # indices = ones_vec * indices_vec
            # bin value = bin_idx * q + log(d_min)
            d_min_tensor = ones_vec * tf.log(d_min)
            bin_value = q * tf.cast(indices_vec, tf.float32)
            logged = d_min_tensor + bin_value
            mask = tf.round(tf.exp(logged))  # values corresponding to this bin, for comparison
            depth_discretized = tf.cast(tf.equal(mask, depth), tf.int8)

            invalid_depth = tf.sign(depth)
            # generate batch
            images, depths, depths_discretized, invalid_depths = tf.train.shuffle_batch(
                [image, depth, depth_discretized, invalid_depth],
                batch_size=8,
                num_threads=4,
                capacity=40,
                min_after_dequeue=20)

            coord = tf.train.Coordinator()
            threads = tf.train.start_queue_runners(sess=sess, coord=coord)

            images_val, depths_val, depths_discretized_val, invalid_depths_val = sess.run([images, depths, depths_discretized, invalid_depths])
            sess.run(images)

            output_predict(depths_val, images_val, depths_discretized_val, 'kunda')

            coord.request_stop()
            coord.join(threads)
