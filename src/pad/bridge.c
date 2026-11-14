/* GameCube controller and Classic Controller support for Sonic and the Secret Rings.
 *
 * The game reads the GameCube pads itself (PADRead, every frame) and turns each channel's
 * input into one record per frame, but in one of two ways:
 *
 *   - remote mode (a Wii Remote is connected): from the remote's KPAD statuses.  The pad is
 *     ignored, and so is a Classic Controller on the remote.  Story mode steers by tilting the
 *     sideways remote and reads a shake as large accelerometer values.
 *   - pad mode (no Wii Remote): from the GameCube pad, with a button layout and stick handling
 *     the menus and story mode do not understand.
 *
 * Two hooks make a pad behave like a remote:
 *
 *   HOOK_REMOTE  just before the remote-mode converter: rewrites the KPAD statuses so they read
 *                as the remote doing what the pad / Classic Controller does.  The game then runs
 *                them through its own smoothing exactly as it does for a real remote.
 *   HOOK_TOP     at the top of each channel: remembers the GameCube pad, and when no remote is
 *                connected builds the remote's KPAD status itself, runs the remote converter on
 *                it and skips pad mode (GameCube controller only).
 *
 * Either way: the buttons become the remote buttons they stand for, the left stick tilts the
 * remote (left / right steers, forward / back leans) and the C-stick (Classic Controller:
 * right stick) shakes it.  The remote's own buttons keep working; its motion is replaced while
 * a pad is in use, so a remote lying on the table does not steer.
 */
typedef unsigned int u32;
typedef signed int s32;
typedef unsigned short u16;
typedef signed char s8;
typedef unsigned char u8;

/* Wii Remote buttons as KPAD reports them */
#define WM_LEFT  0x0001
#define WM_RIGHT 0x0002
#define WM_DOWN  0x0004
#define WM_UP    0x0008
#define WM_PLUS  0x0010
#define WM_2     0x0100     /* jump / accelerate / confirm */
#define WM_1     0x0200     /* brake / back */
#define WM_B     0x0400
#define WM_A     0x0800
#define WM_MINUS 0x1000
#define WM_HOME  0x8000

/* PADStatus.button */
#define PAD_LEFT  0x0001
#define PAD_RIGHT 0x0002
#define PAD_DOWN  0x0004
#define PAD_UP    0x0008
#define PAD_Z     0x0010
#define PAD_R     0x0020
#define PAD_L     0x0040
#define PAD_A     0x0100
#define PAD_B     0x0200
#define PAD_X     0x0400
#define PAD_Y     0x0800
#define PAD_START 0x1000

/* Classic Controller buttons as KPAD reports them */
#define CL_UP    0x0001
#define CL_LEFT  0x0002
#define CL_ZR    0x0004
#define CL_X     0x0008
#define CL_A     0x0010
#define CL_Y     0x0020
#define CL_B     0x0040
#define CL_ZL    0x0080
#define CL_R     0x0200
#define CL_PLUS  0x0400
#define CL_HOME  0x0800
#define CL_MINUS 0x1000
#define CL_L     0x2000
#define CL_DOWN  0x4000
#define CL_RIGHT 0x8000

/* KPADStatus (this SDK) */
#define KPAD_SIZE 0x88
#define K_HOLD    0x00
#define K_ACC     0x0C      /* x, y, z in g; held sideways and flat: (0, -1, 0) */
#define K_DEV     0x5C      /* u32: 0 remote, 1 Nunchuk, 2 Classic Controller */
#define K_CLHOLD  0x60
#define K_CLSTICK 0x6C      /* left stick x, y; the right stick follows */
#define K_ERR     0x85

/* PADStatus */
#define P_ERR     10
#define PAD_ERR_TRANSFER (-3)

/* the hook's own variables, inside its body (zero when installed) */
extern struct state pad_state;
struct state {
    u8 pad[4][12];  /* per port: the last PADStatus that arrived without an error */
    u8 valid[4];
    u32 tick;       /* frames, for the shake's back-and-forth */
    u16 prev[4];    /* per port: last frame's buttons, for press / release (no-remote mode) */
};

/* what the player is doing, whichever controller it came from */
struct in {
    u32 btn;        /* WM_* */
    float sx, sy;   /* left stick, -1..1 */
    float cx, cy;   /* C-stick / right stick, -1..1 */
};

/* the record the game keeps per channel per frame (0x38 bytes) */
struct rec {
    u32 hold, nhold, trig, rel;
    float tilt[3];  /* -acc.x, -acc.z, acc.y of the remote, averaged */
    float f7, f8, f9, f10, f11;
    u32 f12, flags;
};

static inline float absf(float v)
{
    return v < 0 ? -v : v;
}

static inline __attribute__((unused)) float clamp1(float v)
{
    return v > 1.0f ? 1.0f : v < -1.0f ? -1.0f : v;
}

/* a stick axis with the dead zone removed and a gentle curve near the centre */
static __attribute__((unused)) float curve(float v)
{
    const float d = 0.12f;
    float a = absf(v);
    if (a <= d)
        return 0.0f;
    a = (a - d) / (1.0f - d);
    if (a > 1.0f)
        a = 1.0f;
    a = a * (0.35f + 0.65f * a);
    return v < 0 ? -a : a;
}

/* square root without fsqrt (Broadway has none): rsqrte estimate + Newton steps */
static __attribute__((unused)) float sqrtf_(float x)
{
    double y;
    int i;
    if (x <= 0.0f)
        return 0.0f;
    __asm__("frsqrte %0,%1" : "=f"(y) : "f"((double)x));
    for (i = 0; i < 3; i++)
        y = y * (1.5 - 0.5 * x * y * y);
    return (float)(x * y);
}

/* the remote's accelerometer for this input: tilted by the left stick (full stick is about 45
 * degrees), or shaken back and forth while the C-stick is pushed (what a real shake reads as) */
static __attribute__((unused)) void accel(const struct in *v, u32 tick, float *ax, float *ay, float *az)
{
    const float tilt = 0.72f;
    float x, z, y;
    if (absf(v->cx) > 0.5f || absf(v->cy) > 0.5f) {
        float s = (tick & 1) ? 1.0f : -1.0f;
        *ax = 3.4f * s;
        *ay = 2.4f * s;
        *az = -3.4f * s;
        return;
    }
    x = -curve(v->sy) * tilt;       /* lean forward / back */
    z = -curve(v->sx) * tilt;       /* steer left / right */
    y = 1.0f - x * x - z * z;
    *ax = x;
    *ay = -sqrtf_(y > 0 ? y : 0);
    *az = z;
}

#if defined(USE_GC) && !defined(HOOK_PROBE)
/* keep port `chan`'s last good response; 1 while a pad is plugged in */
static int gc_get(struct state *st, const u8 *pad, u32 chan, struct in *v)
{
    s8 err = (s8)pad[P_ERR];
    u8 *c;
    u32 b, o = 0, i;

    if (chan >= 4)
        return 0;
    c = st->pad[chan];
    if (err == 0) {                         /* PAD_ERR_NONE: a fresh response */
        for (i = 0; i < 12; i++)
            c[i] = pad[i];
        st->valid[chan] = 1;
    } else if (err != PAD_ERR_TRANSFER) {   /* "nothing new yet" keeps the last one */
        st->valid[chan] = 0;
    }
    if (!st->valid[chan])
        return 0;

    b = *(u16 *)c;
    if (b & PAD_A) o |= WM_2;
    if (b & PAD_B) o |= WM_1;
    if (b & PAD_X) o |= WM_A;
    if (b & PAD_Y) o |= WM_B;
    if (b & PAD_L) o |= WM_UP;              /* step left */
    if (b & PAD_R) o |= WM_DOWN;            /* step right */
    if (b & PAD_START) o |= WM_PLUS;
    if (b & PAD_Z) o |= WM_MINUS;
    /* the D-pad as it sits on a sideways remote */
    if (b & PAD_UP) o |= WM_RIGHT;
    if (b & PAD_DOWN) o |= WM_LEFT;
    if (b & PAD_LEFT) o |= WM_UP;
    if (b & PAD_RIGHT) o |= WM_DOWN;
    v->btn = o;
    /* PADClamp'd sticks: about +-72 at the corners of the octagon, +-59 for the C-stick */
    v->sx = clamp1((float)(s8)c[2] / 72.0f);
    v->sy = clamp1((float)(s8)c[3] / 72.0f);
    v->cx = clamp1((float)(s8)c[4] / 59.0f);
    v->cy = clamp1((float)(s8)c[5] / 59.0f);
    return 1;
}
#endif

#if defined(USE_GC) && defined(HOOK_REMOTE)
static int gc_cached(struct state *st, u32 chan, struct in *v)
{
    static const u8 none[12] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, (u8)PAD_ERR_TRANSFER, 0};
    if (chan >= 4 || !st->valid[chan])
        return 0;
    return gc_get(st, none, chan, v);       /* "nothing new": reads the cache */
}
#endif

#ifdef HOOK_REMOTE
#ifdef USE_CC
static int cc_get(const u8 *k, struct in *v)
{
    u32 b, o = 0;
    if (*(u32 *)(k + K_DEV) != 2 || k[K_ERR] != 0)
        return 0;
    b = *(u32 *)(k + K_CLHOLD);
    if (b & CL_A) o |= WM_2;
    if (b & CL_B) o |= WM_1;
    if (b & CL_X) o |= WM_A;
    if (b & CL_Y) o |= WM_B;
    if (b & (CL_L | CL_ZL)) o |= WM_UP;
    if (b & (CL_R | CL_ZR)) o |= WM_DOWN;
    if (b & CL_PLUS) o |= WM_PLUS;
    if (b & CL_MINUS) o |= WM_MINUS;
    if (b & CL_HOME) o |= WM_HOME;
    if (b & CL_UP) o |= WM_RIGHT;
    if (b & CL_DOWN) o |= WM_LEFT;
    if (b & CL_LEFT) o |= WM_UP;
    if (b & CL_RIGHT) o |= WM_DOWN;
    v->btn = o;
    v->sx = ((float *)(k + K_CLSTICK))[0];
    v->sy = ((float *)(k + K_CLSTICK))[1];
    v->cx = ((float *)(k + K_CLSTICK))[2];
    v->cy = ((float *)(k + K_CLSTICK))[3];
    return 1;
}
#endif

/* k: this channel's KPAD statuses (k[0] the newest), n of them; returns the new n */
s32 pad_remote(u8 *k, s32 n, u32 chan, struct state *st)
{
    struct in v;
    int used = 0;
    float ax, ay, az;
    s32 i;

    st->tick++;
#ifdef USE_GC
    used = gc_cached(st, chan, &v);
#endif
#ifdef USE_CC
    if (n > 0 && cc_get(k, &v))             /* a Classic Controller wins over the pad */
        used = 1;
#endif
    if (!used)
        return n;
    if (n <= 0)
        return n;
    accel(&v, st->tick, &ax, &ay, &az);
    for (i = 0; i < n; i++) {
        u8 *s = k + i * KPAD_SIZE;
        *(u32 *)(s + K_HOLD) |= v.btn;
        ((float *)(s + K_ACC))[0] = ax;
        ((float *)(s + K_ACC))[1] = ay;
        ((float *)(s + K_ACC))[2] = az;
    }
    return n;
}
#endif

#ifdef HOOK_TOP
/* the game's own functions (addresses given to the linker) */
extern s32 wpad_probe(s32 chan, u32 *type);
extern void game_conv(void *rec, u8 *k, s32 n, u32 chan);

/* top of the pad loop, every channel every frame.  Remembers the channel's GameCube pad, and
 * when there is no Wii Remote on the channel, plays one: builds the KPAD status a remote doing
 * what the pad does would give, runs the game's remote converter on it and returns 1 so the
 * stub skips the rest of the channel (the WPAD calls a missing remote would hang).
 * conn: the game's "a Wii Remote is connected on this channel" byte, which it otherwise only
 * sets from the connect callback; story mode pauses ("Communications with the Wii Remote have
 * been interrupted") while it is clear. */
s32 pad_top(const u8 *pad, u32 chan, u8 *conn, u8 *k, void *rec)
{
    struct state *st = &pad_state;
    struct in v;
    float ax, ay, az;
    u32 type, i;

    if (!gc_get(st, pad, chan, &v))
        return 0;
    if (wpad_probe(chan, &type) != -1)      /* a remote is there (or busy): the usual path */
        return 0;
    st->tick++;
    for (i = 0; i < KPAD_SIZE; i++)
        k[i] = 0;
    accel(&v, st->tick, &ax, &ay, &az);
    *(u32 *)(k + K_HOLD) = v.btn;
    *(u32 *)(k + K_HOLD + 4) = v.btn & ~st->prev[chan];     /* trig */
    *(u32 *)(k + K_HOLD + 8) = st->prev[chan] & ~v.btn;     /* release */
    st->prev[chan] = (u16)v.btn;
    ((float *)(k + K_ACC))[0] = ax;
    ((float *)(k + K_ACC))[1] = ay;
    ((float *)(k + K_ACC))[2] = az;
    game_conv(rec, k, 1, chan);
    ((struct rec *)rec)->flags |= 0x8000;   /* what the loop adds after the converter */
    *conn = 1;
    return 1;
}
#endif
