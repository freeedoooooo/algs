let originalArray = [];
let temporaryArray = [];
const originalContainer = document.getElementById('original-container');
const temporaryContainer = document.getElementById('temporary-container');
let animationSpeed = 1000; // 动画速度，单位毫秒（1秒）
let stepMode = false;
let mergeQueue = [];
let currentMergeTask = null;

function createBars(container, arr) {
    container.innerHTML = '';
    arr.forEach(height => {
        const bar = document.createElement('div');
        bar.className = 'bar';
        const innerBar = document.createElement('div');
        innerBar.style.height = `${height}px`;
        bar.appendChild(innerBar);
        container.appendChild(bar);
    });
}

function startAnimation() {
    resetArray();
    createBars(originalContainer, originalArray);
    createBars(temporaryContainer, temporaryArray);
    stepMode = false;
    mergeSort(0, originalArray.length - 1).then(() => finalizeMerge());
}

function resetAnimation() {
    resetArray();
    createBars(originalContainer, originalArray);
    createBars(temporaryContainer, temporaryArray);
    mergeQueue = [];
    document.getElementById('nextStep').disabled = true;
}

function resetArray() {
    originalArray = Array.from({ length: 50 }, () => Math.floor(Math.random() * 100) + 10);
    temporaryArray = Array.from(originalArray); // 初始化临时数组
    createBars(originalContainer, originalArray);
    createBars(temporaryContainer, temporaryArray);
}

async function mergeSort(start, end) {
    if (start >= end) return;

    const mid = Math.floor((start + end) / 2);
    await mergeSort(start, mid);
    await mergeSort(mid + 1, end);

    await merge(start, mid, end);
}

async function merge(start, mid, end) {
    let left = temporaryArray.slice(start, mid + 1);
    let right = temporaryArray.slice(mid + 1, end + 1);

    let i = 0, j = 0, k = start;
    while (i < left.length && j < right.length) {
        if (left[i] <= right[j]) {
            temporaryArray[k] = left[i];
            i++;
        } else {
            temporaryArray[k] = right[j];
            j++;
        }
        k++;
        await updateTemporaryDOM();
    }

    while (i < left.length) {
        temporaryArray[k] = left[i];
        i++;
        k++;
        await updateTemporaryDOM();
    }

    while (j < right.length) {
        temporaryArray[k] = right[j];
        j++;
        k++;
        await updateTemporaryDOM();
    }
}

async function updateTemporaryDOM() {
    return new Promise(resolve => {
        setTimeout(() => {
            createBars(temporaryContainer, temporaryArray);
            resolve();
        }, animationSpeed / originalArray.length); // 控制动画速度
    });
}

async function finalizeMerge() {
    for (let i = 0; i < originalArray.length; i++) {
        originalArray[i] = temporaryArray[i];
    }
    await updateOriginalDOM();
}

async function updateOriginalDOM() {
    return new Promise(resolve => {
        setTimeout(() => {
            createBars(originalContainer, originalArray);
            resolve();
        }, animationSpeed / originalArray.length); // 控制动画速度
    });
}

function stepByStep() {
    resetArray();
    createBars(originalContainer, originalArray);
    createBars(temporaryContainer, temporaryArray);
    stepMode = true;
    mergeQueue = [];
    currentMergeTask = mergeSort(0, originalArray.length - 1).then(() => finalizeMerge());
}

async function nextMerge() {
    if (mergeQueue.length > 0) {
        const { callback, params } = mergeQueue.shift();
        await callback(...params);
    }
}

function scheduleMerge(callback, ...params) {
    mergeQueue.push({ callback, params });
    document.getElementById('nextStep').disabled = false;
}