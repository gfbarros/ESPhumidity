try:
    import board
    import displayio
    from adafruit_display_text import label
    from adafruit_bitmap_font import bitmap_font
    import adafruit_tca9548a
    import adafruit_sht4x
    import time
    import microcontroller
    from watchdog import WatchDogMode
    from adafruit_max1704x import MAX17048

    # AIO imports
    import adafruit_minimqtt.adafruit_minimqtt as MQTT
    from adafruit_io.adafruit_io import IO_MQTT
    import wifi
    import socketpool

    # set up watchdog timer
    wdt = microcontroller.watchdog
    wdt.timeout = 60
    wdt.mode = WatchDogMode.RESET
    wdt.feed()

    WHITE = 0xFFFFFF
    GREEN = 0x00FF00
    RED = 0xFF0000
    YELLOW = 0xFFFF00
    BLACK = 0x000000

    sht0_found = False
    sht1_found = False
    sht2_found = False
    sht3_found = False
    high_hum = False

    # --- WiFi --- #
    try:
        from secrets import secrets
    except ImportError:
        print("WiFi secrets are kept in secrets.py, please add them there!")
        raise

    # Define callback functions which will be called when certain events happen.
    # pylint: disable=unused-argument
    def connected(client):
        # Connected function will be called when the client is connected to Adafruit IO.
        # This is a good place to subscribe to feed changes.  The client parameter
        # passed to this function is the Adafruit IO MQTT client so you can make
        # calls against it easily.
        #    print("Connected to Adafruit IO!  Listening for DemoFeed changes...")
        print("Connected to Adafruit IO!")
        # Subscribe to changes on a feed named DemoFeed.
        #    client.subscribe("DemoFeed")

    def subscribe(client, userdata, topic, granted_qos):
        # This method is called when the client subscribes to a new feed.
        print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))

    def unsubscribe(client, userdata, topic, pid):
        # This method is called when the client unsubscribes from a feed.
        print("Unsubscribed from {0} with PID {1}".format(topic, pid))

    # pylint: disable=unused-argument
    def disconnected(client):
        # Disconnected function will be called when the client disconnects.
        print("Disconnected from Adafruit IO!")

    # pylint: disable=unused-argument
    def message(client, feed_id, payload):
        # Message function will be called when a subscribed feed has a new value.
        # The feed_id parameter identifies the feed, and the payload parameter has
        # the new value.
        print("Feed {0} received new value: {1}".format(feed_id, payload))

    # Connect to WiFi
    print("Connecting to WiFi...")
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    print("Connected!")

    # Initialize MQTT interface with the esp interface
    pool = socketpool.SocketPool(wifi.radio)

    # Initialize a new MQTT Client object
    mqtt_client = MQTT.MQTT(
        broker="io.adafruit.com",
        port=1883,
        username=secrets["aio_username"],
        password=secrets["aio_key"],
        socket_pool=pool,
    )

    # Initialize an Adafruit IO MQTT Client
    io = IO_MQTT(mqtt_client)

    # Connect the callback methods defined above to Adafruit IO
    io.on_connect = connected
    io.on_disconnect = disconnected
    io.on_subscribe = subscribe
    io.on_unsubscribe = unsubscribe
    io.on_message = message

    # Connect to Adafruit IO
    print("Connecting to Adafruit IO...")
    io.connect()

    # ----Begin sensor code---- #
    display = board.DISPLAY

    i2c = board.STEMMA_I2C()
    mux = adafruit_tca9548a.PCA9546A(i2c)
    max17048 = MAX17048(i2c)

    for channel in range(4):
        if mux[channel].try_lock():
            print("Channel {}: ".format(channel), end="")
            addresses = mux[channel].scan()
            print([hex(address) for address in addresses if address != 0x70])
            mux[channel].unlock()

            if addresses.count(0x44):
                if channel == 0:
                    sht0 = adafruit_sht4x.SHT4x(mux[0])
                    sht0_found = True
                elif channel == 1:
                    sht1 = adafruit_sht4x.SHT4x(mux[1])
                    sht1_found = True
                elif channel == 2:
                    sht2 = adafruit_sht4x.SHT4x(mux[2])
                    sht2_found = True
                elif channel == 3:
                    sht3 = adafruit_sht4x.SHT4x(mux[3])
                    sht3_found = True
            # feed the watchdog
            wdt.feed()

    bg_bitmap = displayio.Bitmap(display.width, display.height, 2)
    bg_palette = displayio.Palette(2)
    bg_palette[0] = WHITE
    bg_palette[1] = YELLOW
    bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)

    display_group = displayio.Group()
    display_group.append(bg_sprite)

    board.DISPLAY.root_group = display_group

    font = bitmap_font.load_font("/fonts/SourceSansPro-Regular-31.bdf")
    text_color = BLACK

    # init text areas
    sht0_text = label.Label(font, text="S0:  -----C    -----%", color=text_color)
    sht0_text.anchor_point = (0.0, 0.0)
    sht0_text.anchored_position = (2, 2)
    sht1_text = label.Label(font, text="S1:  -----C    -----%", color=text_color)
    sht1_text.anchor_point = (0.0, 0.0)
    sht1_text.anchored_position = (2, 30)
    sht2_text = label.Label(font, text="S2:  -----C    -----%", color=text_color)
    sht2_text.anchor_point = (0.0, 0.0)
    sht2_text.anchored_position = (2, 60)
    sht3_text = label.Label(font, text="S3:  -----C    -----%", color=text_color)
    sht3_text.anchor_point = (0.0, 0.0)
    sht3_text.anchored_position = (2, 90)

    display_group.append(sht0_text)
    display_group.append(sht1_text)
    display_group.append(sht2_text)
    display_group.append(sht3_text)

    # ----Sensor read loop---- #
    last0 = 0
    last1 = 0
    last2 = 0
    last3 = 0
    lastB = 0

    while True:
        if sht0_found:
            temp0, hum0 = sht0.measurements
            sht0_text.text = "S0:  {0:.1f}C   {1:.1f}%".format(temp0, hum0)
            if hum0 >= 40:
                sht0_text.color = RED
                high_hum = True
            else:
                sht0_text.color = BLACK
            # Push data to AIO
            if (time.monotonic() - last0) >= 30:
                print("Publishing sht0 to AIO at ", last0)
                io.publish('esp-sensors.sht41-0', hum0)
                io.publish("esp-sensors.sht41-0t", temp0)
                last0 = time.monotonic()

        if sht1_found:
            temp1, hum1 = sht1.measurements
            sht1_text.text = "S1:  {0:.1f}C   {1:.1f}%".format(temp1, hum1)
            if hum1 >= 40:
                sht1_text.color = RED
                high_hum = True
            else:
                sht1_text.color = BLACK
            # Push data to AIO
            if (time.monotonic() - last1) >= 30:
                print("Publishing sht1 to AIO at ", last1)
                io.publish('esp-sensors.sht41-1', hum1)
                io.publish("esp-sensors.sht41-1t", temp1)
                last1 = time.monotonic()

        if sht2_found:
            temp2, hum2 = sht2.measurements
            sht2_text.text = "S2:  {0:.1f}C   {1:.1f}%".format(temp2, hum2)
            if hum2 >= 40:
                sht2_text.color = RED
                high_hum = True
            else:
                sht2_text.color = BLACK
            # Push data to AIO
            if (time.monotonic() - last2) >= 30:
                print("Publishing sht2 to AIO at ", last2)
                io.publish('esp-sensors.sht41-2', hum2)
                io.publish("esp-sensors.sht41-2t", temp2)
                last2 = time.monotonic()

        if sht3_found:
            temp3, hum3 = sht3.measurements
            sht3_text.text = "S3:  {0:.1f}C   {1:.1f}%".format(temp3, hum3)
            if hum3 >= 40:
                sht3_text.color = RED
                high_hum = True
            else:
                sht3_text.color = BLACK
            # Push data to AIO
            if (time.monotonic() - last3) >= 30:
                print("Publishing sht3 to AIO at ", last3)
                io.publish('esp-sensors.sht41-3', hum3)
                io.publish("esp-sensors.sht41-3t", temp3)
                last3 = time.monotonic()

        if high_hum:
            bg_bitmap.fill(1)
        else:
            bg_bitmap.fill(0)
        high_hum = False

        # Check battery monitor & Push data to AIO
        if (time.monotonic() - lastB) >= 30:
            print("Publishing Battery Info to AIO at ", lastB)
            io.publish('esp-sensors.battery', max17048.cell_percent)
            lastB = time.monotonic()
        # print(f"Battery voltage: {max17048.cell_voltage:.2f} Volts")
        # print(f"Battery percentage: {max17048.cell_percent:.1f} %")
        # print("")

        # feed the watchdog
        wdt.feed()
        time.sleep(1)
except:
    # reboot in case of exception
    print("Caught exception, rebooting")
    microcontroller.reset()
