set -e
BASE_DIR="$(pwd)/../programs"
WORK_DIR="$BASE_DIR/builds"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$WORK_DIR" "$LOG_DIR"



function build_project() {
    local url="$1"
    local project_name="$2"
    local build_commands="${@:3}"
    
    echo "========================================================"
    echo "Building $project_name from $url"
    echo "========================================================"
    
    # Create project directory
    mkdir -p "$WORK_DIR/$project_name"
    cd "$WORK_DIR/$project_name"

    # Remove any existing files
    rm -rf *
    
    # Download and extract
    echo "Downloading $project_name..."
    curl -L "$url" -o "${project_name}.tar.gz"
    tar -xzf "${project_name}.tar.gz" --strip-components=1
    rm "${project_name}.tar.gz"
    
    # Execute build commands
    echo "Building $project_name..."
    eval "$build_commands" > "$LOG_DIR/${project_name}_build.log" 2>&1
    
    echo "$project_name build completed"
    cd "$BASE_DIR"
    echo ""
}

# Build SQLite
build_project \
    "https://www.sqlite.org/2025/sqlite-autoconf-3490100.tar.gz" \
    "sqlite" \
    "CFLAGS=\"-O0 -pg -g\" ./configure && 
     make"

# Build Zstandard
build_project \
    "https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz" \
    "zstd" \
    "sed -i.bak 's/^CFLAGS ?= .*/CFLAGS ?= -pg -g -O0/' Makefile && 
     make"

# Build OpenSSL
build_project \
    "https://github.com/openssl/openssl/releases/download/openssl-3.4.1/openssl-3.4.1.tar.gz" \
    "openssl" \
    "./config -d no-asm no-shared -O0 -pg -g && 
     make"

# Build FFmpeg
build_project \
    "https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.gz" \
    "ffmpeg" \
    "CFLAGS=\"-pg -g -O0\" LDFLAGS=\"-pg\" ./configure --disable-optimizations --disable-asm --enable-debug=3 &&
     make"

echo "All builds completed successfully!"
echo "Build logs are available in $LOG_DIR"