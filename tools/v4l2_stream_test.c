/*
 * v4l2_stream_test — minimal V4L2 streaming verification
 *
 * Opens a V4L2 device, requests 1 MMAP buffer, starts streaming,
 * waits up to TIMEOUT_SEC for one frame, then exits.
 * If an output file path is given the raw frame bytes are written there.
 *
 * Exit codes:
 *   0  frame received  → streaming works
 *   1  timeout        → no frame within TIMEOUT_SEC
 *   2  device error   → open/ioctl/mmap failed
 *
 * Usage: v4l2_stream_test /dev/videoX [output_file]
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <linux/videodev2.h>
#include <unistd.h>

#define TIMEOUT_SEC 5

static int xioctl(int fd, unsigned long req, void *arg)
{
    int r;
    do { r = ioctl(fd, req, arg); } while (r == -1 && errno == EINTR);
    return r;
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s /dev/videoX [output_file]\n", argv[0]);
        return 2;
    }

    const char *dev     = argv[1];
    const char *outfile = argc >= 3 ? argv[2] : NULL;
    int fd = open(dev, O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", dev, strerror(errno));
        return 2;
    }

    /* query capabilities */
    struct v4l2_capability cap;
    if (xioctl(fd, VIDIOC_QUERYCAP, &cap) < 0) {
        fprintf(stderr, "VIDIOC_QUERYCAP: %s\n", strerror(errno));
        close(fd); return 2;
    }
    if (!(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE)) {
        fprintf(stderr, "%s: not a capture device\n", dev);
        close(fd); return 2;
    }
    printf("device : %s\n", cap.card);

    /* set format — try MJPEG first, fall back to YUYV */
    struct v4l2_format fmt = {0};
    fmt.type                = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width       = 640;
    fmt.fmt.pix.height      = 480;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
    fmt.fmt.pix.field       = V4L2_FIELD_ANY;
    if (xioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV;
        if (xioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
            fprintf(stderr, "VIDIOC_S_FMT: %s\n", strerror(errno));
            close(fd); return 2;
        }
    }
    printf("format : %dx%d %.4s\n",
           fmt.fmt.pix.width, fmt.fmt.pix.height,
           (char *)&fmt.fmt.pix.pixelformat);

    /* request 1 mmap buffer */
    struct v4l2_requestbuffers req = {0};
    req.count  = 1;
    req.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
        fprintf(stderr, "VIDIOC_REQBUFS: %s\n", strerror(errno));
        close(fd); return 2;
    }

    /* mmap the buffer */
    struct v4l2_buffer buf = {0};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index  = 0;
    if (xioctl(fd, VIDIOC_QUERYBUF, &buf) < 0) {
        fprintf(stderr, "VIDIOC_QUERYBUF: %s\n", strerror(errno));
        close(fd); return 2;
    }
    void *mem = mmap(NULL, buf.length, PROT_READ | PROT_WRITE,
                     MAP_SHARED, fd, buf.m.offset);
    if (mem == MAP_FAILED) {
        fprintf(stderr, "mmap: %s\n", strerror(errno));
        close(fd); return 2;
    }

    /* queue buffer and start streaming */
    if (xioctl(fd, VIDIOC_QBUF, &buf) < 0) {
        fprintf(stderr, "VIDIOC_QBUF: %s\n", strerror(errno));
        close(fd); return 2;
    }
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(fd, VIDIOC_STREAMON, &type) < 0) {
        fprintf(stderr, "VIDIOC_STREAMON: %s\n", strerror(errno));
        close(fd); return 2;
    }

    /* wait for first frame */
    fd_set fds;
    struct timeval tv = { .tv_sec = TIMEOUT_SEC, .tv_usec = 0 };
    FD_ZERO(&fds);
    FD_SET(fd, &fds);
    int r = select(fd + 1, &fds, NULL, NULL, &tv);
    if (r < 0) {
        fprintf(stderr, "select: %s\n", strerror(errno));
        close(fd); return 2;
    }
    if (r == 0) {
        fprintf(stderr, "timeout: no frame in %ds\n", TIMEOUT_SEC);
        close(fd); return 1;
    }

    /* dequeue to confirm frame arrived */
    memset(&buf, 0, sizeof(buf));
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
        fprintf(stderr, "VIDIOC_DQBUF: %s\n", strerror(errno));
        close(fd); return 2;
    }
    printf("frame  : %u bytes — streaming OK\n", buf.bytesused);

    /* write frame to file if requested */
    if (outfile) {
        FILE *f = fopen(outfile, "wb");
        if (f) {
            fwrite(mem, 1, buf.bytesused, f);
            fclose(f);
            printf("saved  : %s\n", outfile);
        } else {
            fprintf(stderr, "fopen %s: %s\n", outfile, strerror(errno));
        }
    }

    xioctl(fd, VIDIOC_STREAMOFF, &type);
    munmap(mem, buf.length);
    close(fd);
    return 0;
}
