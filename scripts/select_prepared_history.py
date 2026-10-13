"""Select a reviewed unused reserve before consuming text-provider quota."""
from __future__ import annotations
import json
import os
from pathlib import Path
try:
    from scripts import generate_script as generator
    from scripts.topic_history import TopicHistory, find_duplicate
except ModuleNotFoundError:
    import generate_script as generator
    from topic_history import TopicHistory, find_duplicate


def select_reserve(directory: Path, entries: list[dict]) -> dict | None:
    for path in sorted(directory.glob('*.json')):
        try:
            episode = json.loads(path.read_text(encoding='utf-8'))
            if (not episode.get('reviewed_on') or not episode.get('source_reference')
                    or generator.validate_episode(episode)
                    or generator.historical_errors(episode)
                    or find_duplicate(episode, entries)):
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        return episode
    return None


def main():
    episode = select_reserve(
        generator.SCRIPT_DIR.parent / 'config/prepared_history',
        TopicHistory(generator.TOPIC_HISTORY_PATH).entries,
    )
    if episode:
        generator.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        generator.OUTPUT_PATH.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Selected reviewed unused reserve:', episode['title'])
    else:
        print('No valid unused reserve; use text generation')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'usable={str(bool(episode)).lower()}\n')


if __name__ == '__main__':
    main()
