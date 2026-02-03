FROM elabftw/elabimg:5.3.11

# Install Python for initialization
RUN apk add --no-cache python3 py3-pip curl

# Install Python dependencies for init script
RUN pip3 install --break-system-packages bcrypt mysql-connector-python

# Copy initialization script
COPY init_elabftw.py /usr/local/bin/init_elabftw.py
RUN chmod +x /usr/local/bin/init_elabftw.py

# Create s6-overlay v3 oneshot service to run init script
# s6-overlay v3 uses a different structure than v2
RUN mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d && \
    mkdir -p /etc/s6-overlay/s6-rc.d/init-nexuslims-user

# Create the oneshot service 'up' file (using execline to call Python directly)
RUN printf '#!/command/execlineb -P\npython3 /usr/local/bin/init_elabftw.py\n' > /etc/s6-overlay/s6-rc.d/init-nexuslims-user/up && \
    chmod +x /etc/s6-overlay/s6-rc.d/init-nexuslims-user/up

# Create service type file (oneshot = runs once at startup)
RUN echo "oneshot" > /etc/s6-overlay/s6-rc.d/init-nexuslims-user/type

# Create dependencies file (run after nginx and php services are up)
RUN printf 'nginx\nphp\n' > /etc/s6-overlay/s6-rc.d/init-nexuslims-user/dependencies

# Register the service in the user bundle
RUN touch /etc/s6-overlay/s6-rc.d/user/contents.d/init-nexuslims-user

# Use the original eLabFTW entrypoint
# No need to override - s6-overlay will run our init script automatically
