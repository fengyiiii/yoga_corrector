import React, { useEffect, useMemo, useRef, useState } from 'react';

const MODES = [
  { value: 'correction', label: '基础动作矫正' },
  { value: 'flow', label: '组合动作练习' },
  { value: 'goal', label: '目标导向训练' },
];

const GOALS = [
  { value: 'posture', label: '体态改善' },
  { value: 'fitness', label: '核心力量' },
  { value: 'flexibility', label: '柔韧放松' },
  { value: 'meditation', label: '专注冥想' },
];

const POSES = ['山式', '下犬式', '战士二式', '树式', '儿童式'];

const PLAN_PRESETS = {
  posture: ['山式 2 分钟', '下犬式 3 组', '战士二式 左右各 30 秒', '儿童式 2 分钟'],
  fitness: ['下犬式 4 组', '战士二式 左右各 45 秒', '平板支撑 30 秒', '儿童式 1 分钟'],
  flexibility: ['山式 呼吸调整 1 分钟', '下犬式 1 分钟', '儿童式 2 分钟', '脊柱扭转 2 分钟'],
  meditation: ['山式 觉察呼吸 2 分钟', '儿童式 3 分钟', '坐姿冥想 5 分钟'],
};

const LANDMARK = {
  NOSE: 0,
  LEFT_EAR: 7,
  RIGHT_EAR: 8,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_KNEE: 25,
  RIGHT_KNEE: 26,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
};

const CONNECTIONS = [
  [LANDMARK.NOSE, LANDMARK.LEFT_SHOULDER],
  [LANDMARK.NOSE, LANDMARK.RIGHT_SHOULDER],
  [LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER],
  [LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_ELBOW],
  [LANDMARK.LEFT_ELBOW, LANDMARK.LEFT_WRIST],
  [LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_ELBOW],
  [LANDMARK.RIGHT_ELBOW, LANDMARK.RIGHT_WRIST],
  [LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_HIP],
  [LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_HIP],
  [LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP],
  [LANDMARK.LEFT_HIP, LANDMARK.LEFT_KNEE],
  [LANDMARK.LEFT_KNEE, LANDMARK.LEFT_ANKLE],
  [LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_KNEE],
  [LANDMARK.RIGHT_KNEE, LANDMARK.RIGHT_ANKLE],
];

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function average(values, fallback = 0) {
  const filtered = values.filter((value) => Number.isFinite(value));
  if (!filtered.length) return fallback;
  return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
}

function stddev(values, fallback = 0) {
  const filtered = values.filter((value) => Number.isFinite(value));
  if (!filtered.length) return fallback;
  const avg = average(filtered, 0);
  const variance = average(filtered.map((value) => (value - avg) ** 2), 0);
  return Math.sqrt(variance);
}

function safeRatio(value, denominator, fallback = 0) {
  if (!Number.isFinite(value) || !Number.isFinite(denominator) || Math.abs(denominator) < 1e-6) {
    return fallback;
  }
  return value / denominator;
}

function point(landmarks, index) {
  const target = landmarks?.[index];
  if (!target) return null;
  if (typeof target.visibility === 'number' && target.visibility < 0.35) return null;
  return target;
}

function midpoint(a, b) {
  if (!a || !b) return null;
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
    z: ((a.z || 0) + (b.z || 0)) / 2,
  };
}

function distance(a, b) {
  if (!a || !b) return null;
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function angle(a, b, c) {
  if (!a || !b || !c) return null;
  const abx = a.x - b.x;
  const aby = a.y - b.y;
  const cbx = c.x - b.x;
  const cby = c.y - b.y;
  const dot = abx * cbx + aby * cby;
  const magnitude = Math.hypot(abx, aby) * Math.hypot(cbx, cby);
  if (!magnitude) return null;
  const cosine = clamp(dot / magnitude, -1, 1);
  return (Math.acos(cosine) * 180) / Math.PI;
}

function rangeScore(value, idealMin, idealMax, hardMin, hardMax) {
  if (!Number.isFinite(value)) return 58;
  if (value >= idealMin && value <= idealMax) return 96;
  if (value <= hardMin || value >= hardMax) return 42;
  if (value < idealMin) {
    const ratio = (value - hardMin) / Math.max(idealMin - hardMin, 1e-6);
    return Math.round(42 + ratio * 54);
  }
  const ratio = (hardMax - value) / Math.max(hardMax - idealMax, 1e-6);
  return Math.round(42 + ratio * 54);
}

function inverseScore(value, idealMax, hardMax) {
  return rangeScore(value, 0, idealMax, 0, hardMax);
}

function weightedOverall(partScores) {
  return Math.round(
    partScores.reduce((sum, item) => sum + item.value, 0) / Math.max(partScores.length, 1)
  );
}

function seededNumber(seed, min, max) {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) {
    h = (h << 5) - h + seed.charCodeAt(i);
    h |= 0;
  }
  const normalized = Math.abs(Math.sin(h) * 10000) % 1;
  return Math.round(min + normalized * (max - min));
}

function getGoalAdvice(goal) {
  const suggestionsByGoal = {
    posture: '你本次更适合优先改善脊柱延展与骨盆中立，建议下次先做 3 分钟基础校准再进入正式练习。',
    fitness: '你本次动作控制还不错，建议下次增加保持时长或每组重复次数，强化核心与下肢稳定。',
    flexibility: '你本次主要限制来自后侧链和肩髋打开，建议下次增加动态热身和更长的静态停留。',
    meditation: '本次整体节奏稳定，建议下次在每个体式间加入 3 次深呼吸，提升专注感与放松度。',
  };
  return suggestionsByGoal[goal] || suggestionsByGoal.posture;
}

function buildFallbackAnalysis({ fileName, fileSize, pose, mode, goal, duration, reason = '' }) {
  const seed = `${fileName}-${fileSize}-${pose}-${mode}-${goal}-${duration}`;
  const overall = seededNumber(seed + 'overall', 71, 92);
  const spine = seededNumber(seed + 'spine', 65, 95);
  const shoulder = seededNumber(seed + 'shoulder', 64, 94);
  const hip = seededNumber(seed + 'hip', 62, 93);
  const balance = seededNumber(seed + 'balance', 60, 93);
  const holdTime = Math.max(8, Math.min(45, Math.round((duration || 18) * 0.55)));

  const issueLibrary = {
    山式: [
      '肩膀轻微耸起，建议下沉肩胛并放松颈部。',
      '骨盆中立不够稳定，建议收紧核心避免塌腰。',
      '重心略偏前脚掌，尝试把力量均匀分布到双脚。',
    ],
    下犬式: [
      '背部延展不足，建议继续向后上方推送骨盆。',
      '脚跟抬起较高，可先微屈膝再逐步拉长后侧链。',
      '肩部有轻微塌陷，注意手掌推地让胸腔打开。',
    ],
    战士二式: [
      '前膝弯曲角度不足，可再下沉髋部增强稳定性。',
      '双臂不够水平，注意两侧手臂向外延展。',
      '前膝方向略内扣，需与前脚脚尖方向保持一致。',
    ],
    树式: [
      '站立侧骨盆稳定性偏弱，建议核心持续收紧。',
      '抬腿侧膝部打开不足，髋外展可以再明显一些。',
      '视线焦点不够稳定，建议固定前方一点帮助平衡。',
    ],
    儿童式: [
      '肩背放松不足，可让手臂更自然向前延展。',
      '呼吸节奏稍快，建议用更慢的鼻吸鼻呼进入放松。',
      '髋部下沉不充分，可在舒适范围内更贴近脚跟。',
    ],
  };

  return {
    detectedPose: pose,
    overall,
    holdTime,
    capturedFrames: 0,
    detectionQuality: 0,
    analysisMode: '演示回退模式',
    analysisNote: reason || '真实引擎暂不可用，已自动切换为演示结果。',
    sampleLandmarks: null,
    partScores: [
      { label: '脊柱延展', value: spine },
      { label: '肩部稳定', value: shoulder },
      { label: '髋部打开', value: hip },
      { label: '平衡控制', value: balance },
    ],
    topIssues: issueLibrary[pose].slice(0, 3),
    strengths: [
      overall > 85 ? '动作节奏比较稳定。' : '动作完成度不错。',
      spine > 80 ? '躯干控制较好。' : '核心参与度尚可。',
      balance > 82 ? '平衡表现较稳定。' : '基础重心控制已具备。',
    ],
    summary:
      overall > 85
        ? `你的 ${pose} 完成度较高，当前主要优化点集中在细节控制。`
        : `你的 ${pose} 已经具备基础框架，但还需要在稳定性和对齐度上继续改进。`,
    nextAdvice: getGoalAdvice(goal),
    riskLevel: overall >= 85 ? '低' : overall >= 76 ? '中' : '偏高',
  };
}

function extractFrameMetrics(landmarks) {
  const ls = point(landmarks, LANDMARK.LEFT_SHOULDER);
  const rs = point(landmarks, LANDMARK.RIGHT_SHOULDER);
  const le = point(landmarks, LANDMARK.LEFT_ELBOW);
  const re = point(landmarks, LANDMARK.RIGHT_ELBOW);
  const lw = point(landmarks, LANDMARK.LEFT_WRIST);
  const rw = point(landmarks, LANDMARK.RIGHT_WRIST);
  const lh = point(landmarks, LANDMARK.LEFT_HIP);
  const rh = point(landmarks, LANDMARK.RIGHT_HIP);
  const lk = point(landmarks, LANDMARK.LEFT_KNEE);
  const rk = point(landmarks, LANDMARK.RIGHT_KNEE);
  const la = point(landmarks, LANDMARK.LEFT_ANKLE);
  const ra = point(landmarks, LANDMARK.RIGHT_ANKLE);
  const leEar = point(landmarks, LANDMARK.LEFT_EAR);
  const reEar = point(landmarks, LANDMARK.RIGHT_EAR);
  const nose = point(landmarks, LANDMARK.NOSE);

  const midShoulder = midpoint(ls, rs);
  const midHip = midpoint(lh, rh);
  const midAnkle = midpoint(la, ra);
  const midKnee = midpoint(lk, rk);
  const midWrist = midpoint(lw, rw);

  const shoulderWidth = distance(ls, rs);
  const hipWidth = distance(lh, rh);
  const bodyWidth = shoulderWidth || hipWidth || 0.18;

  const leftElbowAngle = angle(ls, le, lw);
  const rightElbowAngle = angle(rs, re, rw);
  const leftKneeAngle = angle(lh, lk, la);
  const rightKneeAngle = angle(rh, rk, ra);
  const leftHipAngle = angle(ls, lh, lk);
  const rightHipAngle = angle(rs, rh, rk);
  const hipPikeAngle = angle(midShoulder, midHip, midAnkle);
  const hipFoldAngle = angle(midShoulder, midHip, midKnee);
  const leftShoulderFlexion = angle(lh, ls, lw);
  const rightShoulderFlexion = angle(rh, rs, rw);

  return {
    bodyWidth,
    midHipX: midHip?.x,
    torsoTilt: safeRatio(Math.abs((midShoulder?.x || 0) - (midHip?.x || 0)), bodyWidth, 0),
    shoulderLevel: safeRatio(Math.abs((ls?.y || 0) - (rs?.y || 0)), bodyWidth, 0),
    hipLevel: safeRatio(Math.abs((lh?.y || 0) - (rh?.y || 0)), bodyWidth, 0),
    earShoulderGap: safeRatio(
      average([
        leEar && ls ? Math.abs(leEar.y - ls.y) : NaN,
        reEar && rs ? Math.abs(reEar.y - rs.y) : NaN,
      ]),
      bodyWidth,
      0
    ),
    armStraight: average([leftElbowAngle, rightElbowAngle], 150),
    legStraight: average([leftKneeAngle, rightKneeAngle], 150),
    leftKneeAngle,
    rightKneeAngle,
    leftHipAngle,
    rightHipAngle,
    hipPikeAngle,
    hipFoldAngle,
    shoulderFlexion: average([leftShoulderFlexion, rightShoulderFlexion], 145),
    armsLevel: safeRatio(
      average([
        lw && ls ? Math.abs(lw.y - ls.y) : NaN,
        rw && rs ? Math.abs(rw.y - rs.y) : NaN,
      ]),
      bodyWidth,
      0
    ),
    wristSpan: safeRatio(distance(lw, rw), bodyWidth, 0),
    ankleSpan: safeRatio(distance(la, ra), hipWidth || bodyWidth, 0),
    balanceOffset: safeRatio(Math.abs((midHip?.x || 0) - (midAnkle?.x || 0)), bodyWidth, 0),
    torsoDrop: safeRatio((midShoulder?.y || 0) - (midHip?.y || 0), bodyWidth, 0),
    wristAhead: safeRatio(((midShoulder?.y || 0) - (midWrist?.y || 0)), bodyWidth, 0),
    leftKneeToAnkleDx: safeRatio(Math.abs((lk?.x || 0) - (la?.x || 0)), bodyWidth, 0),
    rightKneeToAnkleDx: safeRatio(Math.abs((rk?.x || 0) - (ra?.x || 0)), bodyWidth, 0),
    leftFootLift: safeRatio(((rk?.y || 0) - (la?.y || 0)), bodyWidth, 0),
    rightFootLift: safeRatio(((lk?.y || 0) - (ra?.y || 0)), bodyWidth, 0),
    leftKneeOpen: safeRatio(Math.abs((lk?.x || 0) - (midHip?.x || 0)), bodyWidth, 0),
    rightKneeOpen: safeRatio(Math.abs((rk?.x || 0) - (midHip?.x || 0)), bodyWidth, 0),
    headCentered: safeRatio(Math.abs((nose?.x || 0) - (midHip?.x || 0)), bodyWidth, 0),
  };
}

function summarizeFrames(frames) {
  const metrics = frames.map(extractFrameMetrics);
  const summary = {
    bodyWidth: average(metrics.map((item) => item.bodyWidth), 0.18),
    capturedFrames: metrics.length,
    torsoTilt: average(metrics.map((item) => item.torsoTilt), 0.2),
    shoulderLevel: average(metrics.map((item) => item.shoulderLevel), 0.15),
    hipLevel: average(metrics.map((item) => item.hipLevel), 0.15),
    earShoulderGap: average(metrics.map((item) => item.earShoulderGap), 0.25),
    armStraight: average(metrics.map((item) => item.armStraight), 150),
    legStraight: average(metrics.map((item) => item.legStraight), 150),
    leftKneeAngle: average(metrics.map((item) => item.leftKneeAngle), 160),
    rightKneeAngle: average(metrics.map((item) => item.rightKneeAngle), 160),
    hipPikeAngle: average(metrics.map((item) => item.hipPikeAngle), 110),
    hipFoldAngle: average(metrics.map((item) => item.hipFoldAngle), 90),
    shoulderFlexion: average(metrics.map((item) => item.shoulderFlexion), 145),
    armsLevel: average(metrics.map((item) => item.armsLevel), 0.15),
    wristSpan: average(metrics.map((item) => item.wristSpan), 1.2),
    ankleSpan: average(metrics.map((item) => item.ankleSpan), 1.2),
    balanceOffset: average(metrics.map((item) => item.balanceOffset), 0.15),
    torsoDrop: average(metrics.map((item) => item.torsoDrop), 0.15),
    wristAhead: average(metrics.map((item) => item.wristAhead), 0),
    leftKneeToAnkleDx: average(metrics.map((item) => item.leftKneeToAnkleDx), 0.2),
    rightKneeToAnkleDx: average(metrics.map((item) => item.rightKneeToAnkleDx), 0.2),
    leftFootLift: average(metrics.map((item) => item.leftFootLift), 0),
    rightFootLift: average(metrics.map((item) => item.rightFootLift), 0),
    leftKneeOpen: average(metrics.map((item) => item.leftKneeOpen), 0.25),
    rightKneeOpen: average(metrics.map((item) => item.rightKneeOpen), 0.25),
    headCentered: average(metrics.map((item) => item.headCentered), 0.15),
    balanceDrift: safeRatio(stddev(metrics.map((item) => item.midHipX), 0.01), average(metrics.map((item) => item.bodyWidth), 0.18), 0.12),
  };

  const frontSide = summary.leftKneeAngle < summary.rightKneeAngle ? 'left' : 'right';
  const raisedSide = summary.leftFootLift > summary.rightFootLift ? 'left' : 'right';

  return {
    ...summary,
    frontSide,
    raisedSide,
    frontKneeAngle: frontSide === 'left' ? summary.leftKneeAngle : summary.rightKneeAngle,
    backKneeAngle: frontSide === 'left' ? summary.rightKneeAngle : summary.leftKneeAngle,
    frontKneeOverAnkle: frontSide === 'left' ? summary.leftKneeToAnkleDx : summary.rightKneeToAnkleDx,
    standingKneeAngle: raisedSide === 'left' ? summary.rightKneeAngle : summary.leftKneeAngle,
    raisedKneeAngle: raisedSide === 'left' ? summary.leftKneeAngle : summary.rightKneeAngle,
    footLift: raisedSide === 'left' ? summary.leftFootLift : summary.rightFootLift,
    kneeOpen: raisedSide === 'left' ? summary.leftKneeOpen : summary.rightKneeOpen,
  };
}

function buildStrengths(partScores, pose) {
  const sorted = [...partScores].sort((a, b) => b.value - a.value);
  const strengthLibrary = {
    脊柱延展: `${pose} 的躯干线条比较稳定，动作框架已经建立。`,
    肩部稳定: '上肢支撑与肩带控制相对稳定，可以在此基础上继续微调。',
    髋部打开: '髋部参与度不错，动作的打开感已经开始出现。',
    平衡控制: '重心控制较稳，说明你已经具备不错的基础稳定性。',
  };

  const strengths = sorted
    .filter((item) => item.value >= 80)
    .slice(0, 3)
    .map((item) => strengthLibrary[item.label]);

  if (!strengths.length) {
    return ['基础动作框架已经建立，可以继续通过重复练习提升稳定性。'];
  }

  return strengths;
}

function finalizeAssessment({ pose, goal, partScores, issues, holdTime, summaryText }) {
  const overall = weightedOverall(partScores);
  return {
    detectedPose: pose,
    overall,
    holdTime,
    partScores,
    topIssues: issues.slice(0, 3),
    strengths: buildStrengths(partScores, pose),
    summary: summaryText,
    nextAdvice: getGoalAdvice(goal),
    riskLevel: overall >= 85 ? '低' : overall >= 76 ? '中' : '偏高',
  };
}

function assessMountain(metrics, goal) {
  const spineScore = Math.round((inverseScore(metrics.torsoTilt, 0.18, 0.5) + inverseScore(metrics.headCentered, 0.2, 0.55)) / 2);
  const shoulderScore = Math.round((inverseScore(metrics.shoulderLevel, 0.16, 0.42) + rangeScore(metrics.earShoulderGap, 0.22, 0.9, 0.03, 1.2)) / 2);
  const hipScore = Math.round((inverseScore(metrics.hipLevel, 0.16, 0.42) + rangeScore(metrics.ankleSpan, 0.45, 1.7, 0.15, 2.4)) / 2);
  const balanceScore = Math.round((inverseScore(metrics.balanceDrift, 0.14, 0.4) + inverseScore(metrics.balanceOffset, 0.18, 0.48)) / 2);

  const issues = [];
  if (metrics.torsoTilt > 0.22) issues.push('躯干与骨盆没有完全垂直对齐，站立时可以轻收下腹并延展脊柱。');
  if (metrics.earShoulderGap < 0.2) issues.push('肩颈区域略紧张，建议下沉肩胛，避免耸肩。');
  if (metrics.balanceDrift > 0.16) issues.push('重心在练习过程中有轻微摇晃，双脚受力可以再平均一些。');
  if (issues.length < 3) issues.push('骨盆与双脚的稳定关系还可以继续加强，先把脚底三点受力站稳。');

  return finalizeAssessment({
    pose: '山式',
    goal,
    holdTime: 18,
    partScores: [
      { label: '脊柱延展', value: spineScore },
      { label: '肩部稳定', value: shoulderScore },
      { label: '髋部打开', value: hipScore },
      { label: '平衡控制', value: balanceScore },
    ],
    issues,
    summaryText:
      spineScore >= 82
        ? '你的山式整体站姿比较完整，当前主要优化点在于呼吸与重心的细节控制。'
        : '你的山式基本框架已经形成，但脊柱拉长与站姿稳定性还可以继续加强。',
  });
}

function assessDownDog(metrics, goal) {
  const spineScore = Math.round((rangeScore(metrics.hipPikeAngle, 80, 112, 55, 150) + rangeScore(metrics.shoulderFlexion, 145, 185, 120, 195)) / 2);
  const shoulderScore = Math.round((rangeScore(metrics.armStraight, 158, 185, 130, 192) + rangeScore(metrics.shoulderFlexion, 150, 185, 120, 195)) / 2);
  const hipScore = Math.round((rangeScore(metrics.legStraight, 155, 185, 125, 192) + rangeScore(metrics.hipPikeAngle, 80, 112, 55, 150)) / 2);
  const balanceScore = Math.round((inverseScore(metrics.shoulderLevel, 0.18, 0.45) + inverseScore(metrics.hipLevel, 0.18, 0.45) + inverseScore(metrics.balanceDrift, 0.15, 0.4)) / 3);

  const issues = [];
  if (metrics.hipPikeAngle > 118) issues.push('骨盆抬起还不够明显，下犬式里可以继续把坐骨向后上方送。');
  if (metrics.legStraight < 155) issues.push('下肢后侧链略紧，可以先微屈膝，再优先拉长背部。');
  if (metrics.shoulderFlexion < 150 || metrics.armStraight < 158) issues.push('肩部支撑还可以更主动一些，注意手掌推地并打开胸腔。');
  if (issues.length < 3) issues.push('左右两侧的发力还不够完全对称，呼吸时保持双手双脚均匀发力会更稳定。');

  return finalizeAssessment({
    pose: '下犬式',
    goal,
    holdTime: 22,
    partScores: [
      { label: '脊柱延展', value: spineScore },
      { label: '肩部稳定', value: shoulderScore },
      { label: '髋部打开', value: hipScore },
      { label: '平衡控制', value: balanceScore },
    ],
    issues,
    summaryText:
      spineScore >= 82
        ? '你的下犬式整体形态接近稳定的倒 V 结构，当前更适合继续打磨肩髋与呼吸配合。'
        : '你的下犬式已经具备基础形态，但骨盆上提和肩背延展还需要进一步打开。',
  });
}

function assessWarriorTwo(metrics, goal) {
  const spineScore = Math.round((inverseScore(metrics.torsoTilt, 0.18, 0.46) + inverseScore(metrics.shoulderLevel, 0.2, 0.48)) / 2);
  const shoulderScore = Math.round((inverseScore(metrics.armsLevel, 0.16, 0.42) + rangeScore(metrics.wristSpan, 1.35, 3.5, 0.6, 4.8)) / 2);
  const hipScore = Math.round((rangeScore(metrics.frontKneeAngle, 82, 108, 55, 145) + inverseScore(metrics.frontKneeOverAnkle, 0.24, 0.65)) / 2);
  const balanceScore = Math.round((rangeScore(metrics.backKneeAngle, 158, 185, 128, 192) + inverseScore(metrics.balanceDrift, 0.16, 0.4)) / 2);

  const issues = [];
  if (metrics.frontKneeAngle > 112 || metrics.frontKneeAngle < 78) issues.push('前侧膝关节角度还不够理想，可让前膝更稳定地朝向脚尖。');
  if (metrics.armsLevel > 0.18) issues.push('双臂高度略有起伏，想象手指向两侧持续延展，保持肩线平稳。');
  if (metrics.frontKneeOverAnkle > 0.3) issues.push('前膝与脚踝的垂直关系还可以更整齐，避免膝盖内扣或过度偏移。');
  if (issues.length < 3) issues.push('后腿的伸展与地面支撑还可以更主动，增强整体下盘稳定性。');

  return finalizeAssessment({
    pose: '战士二式',
    goal,
    holdTime: 24,
    partScores: [
      { label: '脊柱延展', value: spineScore },
      { label: '肩部稳定', value: shoulderScore },
      { label: '髋部打开', value: hipScore },
      { label: '平衡控制', value: balanceScore },
    ],
    issues,
    summaryText:
      hipScore >= 82
        ? '你的战士二式下盘结构已经比较稳定，后续主要提升的是手臂延展和躯干控制。'
        : '你的战士二式有较好的基本框架，但前膝对齐与髋部稳定还需要进一步加强。',
  });
}

function assessTree(metrics, goal) {
  const spineScore = Math.round((inverseScore(metrics.torsoTilt, 0.18, 0.46) + inverseScore(metrics.headCentered, 0.18, 0.42)) / 2);
  const shoulderScore = Math.round((inverseScore(metrics.shoulderLevel, 0.16, 0.4) + rangeScore(metrics.earShoulderGap, 0.18, 0.9, 0.03, 1.2)) / 2);
  const hipScore = Math.round((rangeScore(metrics.footLift, 0.18, 1.6, 0.03, 2.0) + rangeScore(metrics.kneeOpen, 0.22, 1.3, 0.03, 1.7)) / 2);
  const balanceScore = Math.round((rangeScore(metrics.standingKneeAngle, 162, 185, 130, 192) + inverseScore(metrics.balanceDrift, 0.12, 0.35) + inverseScore(metrics.balanceOffset, 0.18, 0.45)) / 3);

  const issues = [];
  if (metrics.balanceDrift > 0.14) issues.push('站立侧重心略有摇晃，建议先固定视线，再持续收紧核心。');
  if (metrics.footLift < 0.2) issues.push('抬腿高度还可以再提升一点，在舒适范围内让脚掌更靠近小腿或大腿内侧。');
  if (metrics.kneeOpen < 0.22) issues.push('抬腿侧髋部打开不足，试着让膝盖更自然地向侧方展开。');
  if (issues.length < 3) issues.push('站立腿还可以更主动地向下扎根，帮助上半身保持更轻松的平衡。');

  return finalizeAssessment({
    pose: '树式',
    goal,
    holdTime: 20,
    partScores: [
      { label: '脊柱延展', value: spineScore },
      { label: '肩部稳定', value: shoulderScore },
      { label: '髋部打开', value: hipScore },
      { label: '平衡控制', value: balanceScore },
    ],
    issues,
    summaryText:
      balanceScore >= 82
        ? '你的树式已经具备不错的平衡基础，后续更适合细化髋部打开和呼吸节奏。'
        : '你的树式处在可继续打磨的阶段，站立腿稳定性和抬腿侧髋部打开仍是关键。',
  });
}

function assessChildPose(metrics, goal) {
  const spineScore = Math.round(rangeScore(metrics.hipFoldAngle, 40, 88, 24, 128));
  const shoulderScore = Math.round((rangeScore(metrics.armStraight, 155, 185, 120, 192) + rangeScore(metrics.wristAhead, 0.02, 1.1, -0.2, 1.8)) / 2);
  const hipScore = Math.round((rangeScore(metrics.hipFoldAngle, 40, 88, 24, 128) + rangeScore(metrics.legStraight, 55, 130, 30, 180)) / 2);
  const balanceScore = Math.round((inverseScore(metrics.shoulderLevel, 0.18, 0.44) + inverseScore(metrics.hipLevel, 0.18, 0.44) + rangeScore(metrics.torsoDrop, 0.12, 1.0, -0.1, 1.5)) / 3);

  const issues = [];
  if (metrics.hipFoldAngle > 92) issues.push('髋部折叠还不够充分，可以在舒适前提下让臀部更接近脚跟。');
  if (metrics.armStraight < 155) issues.push('手臂前伸的主动感还可以更明显，帮助肩背更自然地拉长。');
  if (metrics.torsoDrop < 0.14) issues.push('胸腔与腹部还没有完全放松下来，进入体式时可以配合更慢的呼吸。');
  if (issues.length < 3) issues.push('左右两侧放松程度仍有一点差异，建议多停留几个呼吸让身体慢慢沉下去。');

  return finalizeAssessment({
    pose: '儿童式',
    goal,
    holdTime: 28,
    partScores: [
      { label: '脊柱延展', value: spineScore },
      { label: '肩部稳定', value: shoulderScore },
      { label: '髋部打开', value: hipScore },
      { label: '平衡控制', value: balanceScore },
    ],
    issues,
    summaryText:
      spineScore >= 82
        ? '你的儿童式整体放松感不错，接下来主要优化肩背延展和呼吸节奏。'
        : '你的儿童式已经进入放松状态，但髋部折叠和上背释放还可以更充分。',
  });
}

function analyzePoseFromFrames(frames, pose, goal) {
  const metrics = summarizeFrames(frames);
  switch (pose) {
    case '山式':
      return assessMountain(metrics, goal);
    case '下犬式':
      return assessDownDog(metrics, goal);
    case '战士二式':
      return assessWarriorTwo(metrics, goal);
    case '树式':
      return assessTree(metrics, goal);
    case '儿童式':
      return assessChildPose(metrics, goal);
    default:
      return assessMountain(metrics, goal);
  }
}

function Card({ children, className = '' }) {
  return <div className={`rounded-3xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</div>;
}

function ProgressBar({ value }) {
  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
      <div className="h-full rounded-full bg-slate-900 transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}

function Badge({ children, tone = 'default' }) {
  const map = {
    default: 'bg-slate-100 text-slate-700 border-slate-200',
    dark: 'bg-slate-900 text-white border-slate-900',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    blue: 'bg-sky-50 text-sky-700 border-sky-200',
    red: 'bg-rose-50 text-rose-700 border-rose-200',
  };
  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs ${map[tone]}`}>{children}</span>;
}

function PosePreview({ sampleLandmarks, partScores }) {
  if (!sampleLandmarks) {
    return <SkeletonFallback partScores={partScores} />;
  }

  const weakParts = partScores.filter((part) => part.value < 78).map((part) => part.label);
  const shoulderGroup = new Set([LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER, LANDMARK.LEFT_ELBOW, LANDMARK.RIGHT_ELBOW, LANDMARK.LEFT_WRIST, LANDMARK.RIGHT_WRIST]);
  const spineGroup = new Set([LANDMARK.NOSE, LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER, LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP]);
  const hipGroup = new Set([LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP, LANDMARK.LEFT_KNEE, LANDMARK.RIGHT_KNEE]);
  const balanceGroup = new Set([LANDMARK.LEFT_KNEE, LANDMARK.RIGHT_KNEE, LANDMARK.LEFT_ANKLE, LANDMARK.RIGHT_ANKLE]);

  function connectionTone(a, b) {
    if (weakParts.includes('肩部稳定') && shoulderGroup.has(a) && shoulderGroup.has(b)) return '#dc2626';
    if (weakParts.includes('脊柱延展') && spineGroup.has(a) && spineGroup.has(b)) return '#dc2626';
    if (weakParts.includes('髋部打开') && hipGroup.has(a) && hipGroup.has(b)) return '#dc2626';
    if (weakParts.includes('平衡控制') && balanceGroup.has(a) && balanceGroup.has(b)) return '#dc2626';
    return '#0f172a';
  }

  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-800">真实关键点骨架</div>
          <div className="text-xs text-slate-500">基于抽样视频帧绘制，红色区域代表当前重点优化部位</div>
        </div>
        <Badge tone="blue">MediaPipe</Badge>
      </div>
      <svg viewBox="0 0 100 140" className="mx-auto h-[280px] w-full max-w-[260px] rounded-2xl bg-white">
        {CONNECTIONS.map(([from, to]) => {
          const a = sampleLandmarks[from];
          const b = sampleLandmarks[to];
          if (!a || !b) return null;
          if ((typeof a.visibility === 'number' && a.visibility < 0.35) || (typeof b.visibility === 'number' && b.visibility < 0.35)) return null;
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x * 100}
              y1={a.y * 140}
              x2={b.x * 100}
              y2={b.y * 140}
              stroke={connectionTone(from, to)}
              strokeWidth="2.6"
              strokeLinecap="round"
            />
          );
        })}
        {sampleLandmarks.map((landmark, index) => {
          if (!landmark || (typeof landmark.visibility === 'number' && landmark.visibility < 0.35)) return null;
          const isCore = [LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER, LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP].includes(index);
          return (
            <circle
              key={`pt-${index}`}
              cx={landmark.x * 100}
              cy={landmark.y * 140}
              r={isCore ? 1.9 : 1.2}
              fill={isCore ? '#0f172a' : '#64748b'}
            />
          );
        })}
      </svg>
    </div>
  );
}

function SkeletonFallback({ partScores }) {
  const weakParts = partScores.filter((p) => p.value < 78).map((p) => p.label);
  const spineWeak = weakParts.includes('脊柱延展');
  const shoulderWeak = weakParts.includes('肩部稳定');
  const hipWeak = weakParts.includes('髋部打开');
  const balanceWeak = weakParts.includes('平衡控制');

  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-800">动作骨架预览</div>
          <div className="text-xs text-slate-500">真实关键点不可用时显示占位骨架</div>
        </div>
        <Badge>占位骨架</Badge>
      </div>
      <svg viewBox="0 0 240 260" className="mx-auto h-[280px] w-full max-w-[260px]">
        <circle cx="120" cy="35" r="16" fill="white" stroke="#0f172a" strokeWidth="3" />
        <line x1="120" y1="51" x2="120" y2="110" stroke={spineWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="120" y1="65" x2="80" y2="95" stroke={shoulderWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="120" y1="65" x2="160" y2="95" stroke={shoulderWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="80" y1="95" x2="58" y2="140" stroke={shoulderWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="160" y1="95" x2="182" y2="140" stroke={shoulderWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="120" y1="110" x2="88" y2="160" stroke={hipWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="120" y1="110" x2="152" y2="160" stroke={hipWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="88" y1="160" x2="72" y2="220" stroke={balanceWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
        <line x1="152" y1="160" x2="168" y2="220" stroke={balanceWeak ? '#dc2626' : '#0f172a'} strokeWidth="6" strokeLinecap="round" />
      </svg>
    </div>
  );
}

export default function YogaCorrectorWebDemoRunnable() {
  const [tab, setTab] = useState('analyze');
  const [mode, setMode] = useState('correction');
  const [goal, setGoal] = useState('posture');
  const [selectedPose, setSelectedPose] = useState('下犬式');
  const [planName, setPlanName] = useState('居家晨练计划');
  const [weeklyFreq, setWeeklyFreq] = useState('3');
  const [duration, setDuration] = useState('20');
  const [notes, setNotes] = useState('希望改善肩颈紧张和圆肩问题');
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [savedPlans, setSavedPlans] = useState([]);
  const [sessionLength, setSessionLength] = useState(18);
  const [engineStatus, setEngineStatus] = useState('loading');
  const [engineMessage, setEngineMessage] = useState('正在加载真实姿态识别引擎...');
  const videoRef = useRef(null);
  const poseLandmarkerRef = useRef(null);

  useEffect(() => {
    const rawHistory = localStorage.getItem('yoga_demo_history_simple');
    const rawPlans = localStorage.getItem('yoga_demo_plans_simple');
    if (rawHistory) setHistory(JSON.parse(rawHistory));
    if (rawPlans) setSavedPlans(JSON.parse(rawPlans));
  }, []);

  useEffect(() => {
    localStorage.setItem('yoga_demo_history_simple', JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    localStorage.setItem('yoga_demo_plans_simple', JSON.stringify(savedPlans));
  }, [savedPlans]);

  useEffect(() => {
    return () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
  }, [videoUrl]);

  useEffect(() => {
    let cancelled = false;

    async function initPoseEngine() {
      setEngineStatus('loading');
      setEngineMessage('正在加载真实姿态识别引擎...');
      try {
        const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision');
        const vision = await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm');
        const poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
          },
          runningMode: 'VIDEO',
          numPoses: 1,
          minPoseDetectionConfidence: 0.45,
          minPosePresenceConfidence: 0.45,
          minTrackingConfidence: 0.45,
        });

        if (cancelled) {
          poseLandmarker.close?.();
          return;
        }

        poseLandmarkerRef.current = poseLandmarker;
        setEngineStatus('ready');
        setEngineMessage('真实姿态识别已就绪，分析时会优先使用 MediaPipe。');
      } catch (error) {
        if (cancelled) return;
        setEngineStatus('error');
        setEngineMessage('真实姿态引擎加载失败，分析时将自动回退到演示模式。');
      }
    }

    initPoseEngine();

    return () => {
      cancelled = true;
      poseLandmarkerRef.current?.close?.();
    };
  }, []);

  const recommendedPlan = useMemo(() => PLAN_PRESETS[goal] || [], [goal]);
  const latestScore = history[0]?.overall || '--';
  const avgScore = history.length ? Math.round(history.reduce((sum, item) => sum + item.overall, 0) / history.length) : '--';
  const postureRiskCount = history.filter((item) => item.riskLevel !== '低').length;

  function onUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    const nextUrl = URL.createObjectURL(file);
    setVideoFile(file);
    setVideoUrl(nextUrl);
    setResult(null);
    setAnalysisProgress(0);
  }

  function onLoadedMetadata() {
    const durationSec = Math.round(videoRef.current?.duration || 18);
    setSessionLength(durationSec);
  }

  async function createDetachedVideo(url) {
    return new Promise((resolve, reject) => {
      const video = document.createElement('video');
      video.src = url;
      video.muted = true;
      video.preload = 'auto';
      video.playsInline = true;
      video.crossOrigin = 'anonymous';
      video.onloadedmetadata = () => resolve(video);
      video.onerror = () => reject(new Error('视频加载失败，暂时无法进行姿态分析。'));
    });
  }

  async function seekVideo(video, time) {
    return new Promise((resolve, reject) => {
      const targetTime = clamp(time, 0.02, Math.max(video.duration - 0.02, 0.02));
      const cleanup = () => {
        video.removeEventListener('seeked', handleSeeked);
        video.removeEventListener('error', handleError);
      };
      const handleSeeked = () => {
        cleanup();
        resolve();
      };
      const handleError = () => {
        cleanup();
        reject(new Error('视频抽帧失败。'));
      };
      video.addEventListener('seeked', handleSeeked, { once: true });
      video.addEventListener('error', handleError, { once: true });
      video.currentTime = targetTime;
    });
  }

  function detectFrame(video, timestampMs) {
    const detector = poseLandmarkerRef.current;
    if (!detector) throw new Error('姿态引擎尚未初始化完成。');
    try {
      return detector.detectForVideo(video, timestampMs);
    } catch (error) {
      return detector.detectForVideo(video);
    }
  }

  async function analyzeWithRealPose(url, pose, goalValue) {
    const previewVideo = await createDetachedVideo(url);
    const effectiveDuration = Math.max(1, Math.min(previewVideo.duration || sessionLength || 8, 12));
    const sampleCount = clamp(Math.round(effectiveDuration / 0.5), 8, 18);
    const sampleTimes = Array.from({ length: sampleCount }, (_, index) => {
      if (sampleCount === 1) return 0.1;
      return 0.1 + ((effectiveDuration - 0.2) * index) / (sampleCount - 1);
    });

    const capturedLandmarks = [];

    for (let index = 0; index < sampleTimes.length; index += 1) {
      const time = sampleTimes[index];
      await seekVideo(previewVideo, time);
      const detection = detectFrame(previewVideo, time * 1000);
      if (detection?.landmarks?.[0]?.length) {
        capturedLandmarks.push(detection.landmarks[0]);
      }
      setAnalysisProgress(Math.round(14 + ((index + 1) / sampleTimes.length) * 72));
      await sleep(20);
    }

    if (capturedLandmarks.length < Math.max(4, Math.floor(sampleTimes.length * 0.35))) {
      throw new Error('没有稳定识别到足够的人体关键点。');
    }

    const previewLandmarks = capturedLandmarks[Math.floor(capturedLandmarks.length / 2)];
    const assessed = analyzePoseFromFrames(capturedLandmarks, pose, goalValue);

    return {
      ...assessed,
      analysisMode: '真实姿态识别',
      analysisNote: '本次结果来自 MediaPipe 抽帧关键点分析。',
      sampleLandmarks: previewLandmarks,
      capturedFrames: capturedLandmarks.length,
      detectionQuality: Math.round((capturedLandmarks.length / sampleTimes.length) * 100),
    };
  }

  async function animateFallbackProgress() {
    const checkpoints = [16, 28, 42, 58, 76, 92, 100];
    for (const checkpoint of checkpoints) {
      setAnalysisProgress(checkpoint);
      await sleep(120);
    }
  }

  async function analyzeVideo() {
    if (!videoFile) return;
    setAnalyzing(true);
    setResult(null);
    setAnalysisProgress(6);

    try {
      let analysis;
      if (engineStatus === 'ready' && videoUrl) {
        analysis = await analyzeWithRealPose(videoUrl, selectedPose, goal);
      } else {
        await animateFallbackProgress();
        analysis = buildFallbackAnalysis({
          fileName: videoFile.name,
          fileSize: String(videoFile.size),
          pose: selectedPose,
          mode,
          goal,
          duration: sessionLength,
          reason: engineStatus === 'loading' ? '真实引擎仍在加载，暂时使用演示结果。' : engineMessage,
        });
      }

      setAnalysisProgress(100);
      setResult({
        ...analysis,
        createdAt: new Date().toISOString(),
        planName,
        mode,
        goal,
        videoName: videoFile.name,
      });
    } catch (error) {
      await animateFallbackProgress();
      const fallback = buildFallbackAnalysis({
        fileName: videoFile?.name || 'demo-video',
        fileSize: String(videoFile?.size || 0),
        pose: selectedPose,
        mode,
        goal,
        duration: sessionLength,
        reason: `${error?.message || '真实分析失败'} 已自动切换为演示结果。`,
      });
      setResult({
        ...fallback,
        createdAt: new Date().toISOString(),
        planName,
        mode,
        goal,
        videoName: videoFile?.name || 'demo-video',
      });
    } finally {
      setAnalyzing(false);
    }
  }

  function saveSession() {
    if (!result) return;
    setHistory((prev) => [result, ...prev].slice(0, 8));
    setTab('history');
  }

  function savePlan() {
    const plan = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      planName,
      goal,
      mode,
      weeklyFreq,
      duration,
      notes,
      recommendedPlan,
      createdAt: new Date().toISOString(),
    };
    setSavedPlans((prev) => [plan, ...prev]);
    setTab('plans');
  }

  function deletePlan(id) {
    setSavedPlans((prev) => prev.filter((item) => item.id !== id));
  }

  function resetHistory() {
    setHistory([]);
    setResult(null);
  }

  const engineTone = engineStatus === 'ready' ? 'green' : engineStatus === 'loading' ? 'blue' : 'amber';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-white to-emerald-50 text-slate-900">
      <div className="mx-auto max-w-7xl p-4 md:p-8">
        <div className="mb-8 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-[28px] bg-slate-950 p-8 text-white shadow-xl">
            <div className="mb-4 inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-sm">AI Yoga Corrector Demo</div>
            <h1 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">
              上传一段瑜伽视频，获得真实关键点分析、矫正建议，并沉淀成个人训练计划。
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 md:text-base">
              当前版本优先使用真实姿态识别引擎抽帧分析视频；如果浏览器环境无法加载模型，会自动回退到演示模式，保证页面始终可运行。
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Badge tone="dark">真实关键点分析</Badge>
              <Badge tone="dark">动作纠错</Badge>
              <Badge tone="dark">训练计划</Badge>
              <Badge tone="dark">历史趋势</Badge>
            </div>
          </div>

          <div className="grid gap-4">
            <Card className="p-5">
              <div className="text-sm text-slate-500">最近一次评分</div>
              <div className="mt-2 text-2xl font-semibold">{latestScore === '--' ? '--' : `${latestScore} 分`}</div>
            </Card>
            <Card className="p-5">
              <div className="text-sm text-slate-500">平均动作评分</div>
              <div className="mt-2 text-2xl font-semibold">{avgScore === '--' ? '--' : `${avgScore} 分`}</div>
            </Card>
            <Card className="p-5">
              <div className="text-sm text-slate-500">需重点改善次数</div>
              <div className="mt-2 text-2xl font-semibold">{postureRiskCount}</div>
            </Card>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          {[
            { key: 'analyze', label: '动作分析' },
            { key: 'plans', label: '训练计划' },
            { key: 'history', label: '历史记录' },
          ].map((item) => (
            <button
              key={item.key}
              onClick={() => setTab(item.key)}
              className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${tab === item.key ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-700'}`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === 'analyze' && (
          <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
            <Card>
              <div className="p-6 md:p-7">
                <h2 className="text-xl font-semibold">1. 配置训练场景</h2>
                <p className="mt-1 text-sm text-slate-500">选择模式、目标和示范动作，再上传一段视频开始分析。</p>

                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-700">姿态引擎状态</div>
                    <Badge tone={engineTone}>
                      {engineStatus === 'ready' ? '真实引擎已就绪' : engineStatus === 'loading' ? '引擎加载中' : '自动回退模式'}
                    </Badge>
                  </div>
                  <div className="text-sm leading-6 text-slate-600">{engineMessage}</div>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium">训练模式</label>
                    <select value={mode} onChange={(event) => setMode(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none">
                      {MODES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium">训练目标</label>
                    <select value={goal} onChange={(event) => setGoal(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none">
                      {GOALS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </div>
                </div>

                <div className="mt-5">
                  <label className="mb-2 block text-sm font-medium">待分析动作</label>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                    {POSES.map((pose) => (
                      <button
                        key={pose}
                        onClick={() => setSelectedPose(pose)}
                        className={`rounded-2xl border px-4 py-3 text-sm transition ${selectedPose === pose ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
                      >
                        {pose}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <label className="mb-2 block text-sm font-medium">上传练习视频</label>
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition hover:bg-slate-100">
                    <div className="text-base font-semibold">点击上传 MP4 / MOV 视频</div>
                    <div className="mt-1 text-xs text-slate-500">建议录制 15–30 秒单个动作片段，人物尽量完整出现在画面中</div>
                    <input type="file" accept="video/*" className="hidden" onChange={onUpload} />
                  </label>
                </div>

                {videoUrl && (
                  <div className="mt-5">
                    <div className="mb-2 text-sm font-medium text-slate-700">已载入视频：{videoFile?.name}</div>
                    <video ref={videoRef} src={videoUrl} controls onLoadedMetadata={onLoadedMetadata} className="aspect-video w-full rounded-[20px] border bg-black" />
                  </div>
                )}

                <div className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                  页面会优先尝试真实抽帧姿态分析；如果模型加载失败或视频中无法稳定识别人体，会自动回退到演示模式，避免 demo 中断。
                </div>

                <button
                  onClick={analyzeVideo}
                  disabled={!videoFile || analyzing}
                  className="mt-5 h-12 w-full rounded-2xl bg-slate-900 text-base font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {analyzing ? '正在分析动作...' : '开始动作分析'}
                </button>

                {analyzing && (
                  <div className="mt-4">
                    <div className="mb-2 flex items-center justify-between text-sm text-slate-600">
                      <span>姿态比对与建议生成中</span>
                      <span>{analysisProgress}%</span>
                    </div>
                    <ProgressBar value={analysisProgress} />
                  </div>
                )}
              </div>
            </Card>

            <Card>
              <div className="p-6 md:p-7">
                <h2 className="text-xl font-semibold">2. AI 矫正结果</h2>
                <p className="mt-1 text-sm text-slate-500">分部位评分、问题诊断与动作建议。</p>

                {!result ? (
                  <div className="mt-6 rounded-[24px] border border-dashed bg-slate-50 p-10 text-center text-slate-500">
                    上传视频并点击“开始动作分析”后，这里会显示真实关键点骨架、动作评分和纠正建议。
                  </div>
                ) : (
                  <div className="mt-6 space-y-6">
                    <div className="grid gap-4 md:grid-cols-3">
                      <div className="rounded-3xl bg-slate-950 p-5 text-white">
                        <div className="text-sm text-slate-300">识别动作</div>
                        <div className="mt-2 text-2xl font-semibold">{result.detectedPose}</div>
                      </div>
                      <div className="rounded-3xl bg-emerald-50 p-5">
                        <div className="text-sm text-slate-500">动作评分</div>
                        <div className="mt-2 text-2xl font-semibold text-emerald-700">{result.overall} / 100</div>
                      </div>
                      <div className="rounded-3xl bg-amber-50 p-5">
                        <div className="text-sm text-slate-500">风险等级</div>
                        <div className="mt-2 text-2xl font-semibold text-amber-700">{result.riskLevel}</div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Badge tone={result.analysisMode === '真实姿态识别' ? 'green' : 'amber'}>{result.analysisMode}</Badge>
                      <Badge>抽取关键帧：{result.capturedFrames}</Badge>
                      <Badge>识别质量：{result.detectionQuality}%</Badge>
                    </div>

                    <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">{result.analysisNote}</div>

                    <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
                      <PosePreview sampleLandmarks={result.sampleLandmarks} partScores={result.partScores} />
                      <div className="space-y-4">
                        {result.partScores.map((part) => (
                          <div key={part.label} className="rounded-2xl border p-4">
                            <div className="mb-2 flex items-center justify-between text-sm font-medium">
                              <span>{part.label}</span>
                              <span>{part.value} 分</span>
                            </div>
                            <ProgressBar value={part.value} />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2">
                      <div className="rounded-3xl border bg-white p-5">
                        <div className="mb-3 text-base font-semibold">需要纠正的地方</div>
                        <div className="space-y-3 text-sm text-slate-700">
                          {result.topIssues.map((issue) => (
                            <div key={issue} className="rounded-2xl bg-amber-50 p-3">{issue}</div>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-3xl border bg-white p-5">
                        <div className="mb-3 text-base font-semibold">做得不错的地方</div>
                        <div className="space-y-3 text-sm text-slate-700">
                          {result.strengths.map((strength) => (
                            <div key={strength} className="rounded-2xl bg-emerald-50 p-3">{strength}</div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="rounded-3xl bg-slate-50 p-5">
                      <div className="text-base font-semibold">总结与下次建议</div>
                      <p className="mt-3 text-sm leading-6 text-slate-700">{result.summary}</p>
                      <p className="mt-3 text-sm leading-6 text-slate-700">{result.nextAdvice}</p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Badge>保持时长：{result.holdTime}s</Badge>
                        <Badge>{MODES.find((item) => item.value === mode)?.label}</Badge>
                        <Badge>{GOALS.find((item) => item.value === goal)?.label}</Badge>
                      </div>
                    </div>

                    <button onClick={saveSession} className="rounded-2xl bg-slate-900 px-5 py-3 text-white">保存本次训练记录</button>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}

        {tab === 'plans' && (
          <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
            <Card>
              <div className="p-6 md:p-7">
                <h2 className="text-xl font-semibold">3. 创建训练计划</h2>
                <p className="mt-1 text-sm text-slate-500">把目标、频率和动作建议一起保存，形成长期练习方案。</p>

                <div className="mt-5 space-y-4">
                  <div>
                    <label className="mb-2 block text-sm font-medium">计划名称</label>
                    <input value={planName} onChange={(event) => setPlanName(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none" />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm font-medium">每周频率</label>
                      <input value={weeklyFreq} onChange={(event) => setWeeklyFreq(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none" />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium">单次时长（分钟）</label>
                      <input value={duration} onChange={(event) => setDuration(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none" />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium">补充目标说明</label>
                    <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="min-h-[120px] w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none" />
                  </div>

                  <div className="rounded-3xl bg-emerald-50 p-5">
                    <div className="mb-3 text-base font-semibold text-emerald-800">AI 推荐动作清单</div>
                    <div className="space-y-2 text-sm text-slate-700">
                      {recommendedPlan.map((item) => <div key={item} className="rounded-2xl bg-white px-3 py-2">{item}</div>)}
                    </div>
                  </div>

                  <button onClick={savePlan} className="h-12 w-full rounded-2xl bg-slate-900 text-base font-medium text-white">保存训练计划</button>
                </div>
              </div>
            </Card>

            <Card>
              <div className="p-6 md:p-7">
                <h2 className="text-xl font-semibold">已保存计划</h2>
                <p className="mt-1 text-sm text-slate-500">用来展示用户长期训练计划和个性化推荐沉淀。</p>

                {savedPlans.length === 0 ? (
                  <div className="mt-6 rounded-[24px] border border-dashed bg-slate-50 p-10 text-center text-slate-500">
                    还没有保存计划。先在左侧填写目标与频率，保存一份居家训练方案。
                  </div>
                ) : (
                  <div className="mt-6 space-y-4">
                    {savedPlans.map((plan) => (
                      <div key={plan.id} className="rounded-[24px] border bg-white p-5 shadow-sm">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div>
                            <div className="text-lg font-semibold">{plan.planName}</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Badge>{GOALS.find((item) => item.value === plan.goal)?.label}</Badge>
                              <Badge>每周 {plan.weeklyFreq} 次</Badge>
                              <Badge>每次 {plan.duration} 分钟</Badge>
                            </div>
                          </div>
                          <button onClick={() => deletePlan(plan.id)} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm">删除</button>
                        </div>
                        <p className="mt-4 text-sm leading-6 text-slate-600">{plan.notes}</p>
                        <div className="mt-4 grid gap-2 md:grid-cols-2">
                          {plan.recommendedPlan.map((item) => <div key={item} className="rounded-2xl bg-slate-50 px-3 py-2 text-sm">{item}</div>)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}

        {tab === 'history' && (
          <Card>
            <div className="p-6 md:p-7">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold">4. 训练历史与进步趋势</h2>
                  <p className="mt-1 text-sm text-slate-500">展示用户动作评分、风险等级和累计改进效果。</p>
                </div>
                <button onClick={resetHistory} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">清空历史</button>
              </div>

              {history.length === 0 ? (
                <div className="mt-6 rounded-[24px] border border-dashed bg-slate-50 p-10 text-center text-slate-500">
                  还没有历史训练记录。先去“动作分析”完成一次视频分析并保存。
                </div>
              ) : (
                <div className="mt-6 grid gap-4">
                  {history.map((item, index) => (
                    <div key={`${item.createdAt}-${index}`} className="grid gap-4 rounded-[24px] border bg-white p-5 lg:grid-cols-[0.7fr_1.3fr]">
                      <div>
                        <div className="text-sm text-slate-500">第 {history.length - index} 次训练</div>
                        <div className="mt-2 text-xl font-semibold">{item.detectedPose}</div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Badge>{item.overall} 分</Badge>
                          <Badge tone={item.riskLevel === '低' ? 'green' : 'amber'}>风险：{item.riskLevel}</Badge>
                          <Badge tone={item.analysisMode === '真实姿态识别' ? 'blue' : 'default'}>{item.analysisMode}</Badge>
                        </div>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-2xl bg-slate-50 p-4">
                          <div className="mb-2 text-sm font-medium">主要问题</div>
                          <div className="space-y-2 text-sm text-slate-600">
                            {item.topIssues.slice(0, 2).map((issue) => <div key={issue}>{issue}</div>)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-emerald-50 p-4">
                          <div className="mb-2 text-sm font-medium text-emerald-800">下次建议</div>
                          <div className="text-sm leading-6 text-slate-700">{item.nextAdvice}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
