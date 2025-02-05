const canvas = document.getElementById('sortCanvas');
const ctx = canvas.getContext('2d');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const rewindBtn = document.getElementById('rewindBtn');
const resetBtn = document.getElementById('resetBtn');

let array = Array.from({length: 50}, () => Math.floor(Math.random() * 400));
let states = {};
let animationId;
let sortPromise;
let paused = false;

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const rectWidth = canvas.width / array.length;
    array.forEach((value, i) => {
        ctx.fillStyle = states[i] === 'sorted' ? 'green' : states[i] === 'comparing' ? 'red' : 'blue';
        ctx.fillRect(i * rectWidth, canvas.height - value, rectWidth, value);
    });

    if (!paused) {
        animationId = requestAnimationFrame(draw);
    }
}

async function quickSort(low, high) {
    if (low < high && !paused) {
        let pi = await randomizedPartition(low, high);
        states[pi] = 'sorted';
        await Promise.all([
            quickSort(low, pi - 1),
            quickSort(pi + 1, high)
        ]);
    }
}

async function randomizedPartition(low, high) {
    if (paused) return;

    let randomIndex = Math.floor(Math.random() * (high - low + 1)) + low;
    [array[randomIndex], array[high]] = [array[high], array[randomIndex]];

    return partition(low, high);
}

async function partition(low, high) {
    let pivot = array[high];
    let i = low - 1;

    for (let j = low; j < high; j++) {
        if (paused) return;
        if (array[j] < pivot) {
            i++;
            [array[i], array[j]] = [array[j], array[i]];
            states[i] = 'comparing';
            states[j] = 'comparing';
            await sleep(50); // 延迟以观察动画
        }
    }

    [array[i + 1], array[high]] = [array[high], array[i + 1]];
    return i + 1;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function startSorting() {
    paused = false;
    sortPromise = quickSort(0, array.length - 1);
    draw();
}

function pauseSorting() {
    paused = true;
}

function rewindSorting() {
    cancelAnimationFrame(animationId);
    paused = true;
    array = Array.from({length: 50}, () => Math.floor(Math.random() * 400));
    states = {};
    draw();
}

function resetSorting() {
    cancelAnimationFrame(animationId);
    paused = true;
    array = Array.from({length: 50}, () => Math.floor(Math.random() * 400));
    states = {};
    draw();
}

startBtn.addEventListener('click', startSorting);
pauseBtn.addEventListener('click', pauseSorting);
rewindBtn.addEventListener('click', rewindSorting);
resetBtn.addEventListener('click', resetSorting);

draw(); // 初始化绘制