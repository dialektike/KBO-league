"""KBO 수집 데이터를 별도 저장소로 rsync 백업하는 스크립트

config.ini의 [backup] target_dir 경로로 data/game/, data/schedule/을 동기화합니다.
--delete 옵션으로 미러링되며, 커밋/푸시는 이 스크립트가 수행하지 않습니다.

Usage:
    python backup.py           # 실제 동기화
    python backup.py --dry-run # 변경 내역만 출력 (실제 변경 없음)

백업 후 수동 커밋:
    cd <target_dir>
    git add -A
    git commit -m "백업 $(date +%Y-%m-%d)"
    git push
"""

import argparse
import os
import subprocess
import sys

import settings

# 백업 대상 하위 경로 (base_dir 기준)
SYNC_PATHS = ["data/game", "data/schedule"]


def run_rsync(src, dst, dry_run=False):
    """rsync로 src → dst 미러링 (--delete)."""
    # trailing slash: src 디렉토리의 "내용"을 dst로 복사
    src = src.rstrip("/") + "/"
    dst = dst.rstrip("/") + "/"

    cmd = ["rsync", "-av", "--delete"]
    if dry_run:
        cmd.append("-n")
    cmd += [src, dst]

    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="KBO 수집 데이터 백업")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="실제 변경 없이 예상 동작만 출력")
    args = parser.parse_args()

    target = settings.BACKUP_TARGET_DIR
    if not target:
        sys.exit("오류: config.ini의 [backup] target_dir이 설정되어 있지 않습니다.")

    if not os.path.isdir(target):
        sys.exit(f"오류: 백업 대상 디렉토리가 존재하지 않습니다: {target}")

    if not os.path.isdir(os.path.join(target, ".git")):
        sys.exit(f"오류: 백업 대상이 git 저장소가 아닙니다: {target}")

    print(f"백업 대상: {target}")
    if args.dry_run:
        print("(dry-run 모드 — 실제 변경은 발생하지 않습니다)")
    print()

    base = settings.BASE_DIR
    any_failed = False

    for sub in SYNC_PATHS:
        src = os.path.join(base, sub)
        dst = os.path.join(target, sub)

        if not os.path.isdir(src):
            print(f"건너뜀 (소스 없음): {src}\n")
            continue

        os.makedirs(dst, exist_ok=True)

        print(f"=== {sub} ===")
        rc = run_rsync(src, dst, dry_run=args.dry_run)
        if rc != 0:
            print(f"  rsync 실패 (exit {rc})")
            any_failed = True
        print()

    if any_failed:
        sys.exit("일부 동기화 실패")

    if args.dry_run:
        print("dry-run 완료")
        return

    print("=" * 40)
    print("백업 완료. 다음 단계 (수동):")
    print(f"  cd {target}")
    print(f"  git add -A")
    print(f"  git commit -m \"백업 $(date +%Y-%m-%d)\"")
    print(f"  git push")


if __name__ == "__main__":
    main()
