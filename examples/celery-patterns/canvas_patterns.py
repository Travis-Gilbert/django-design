"""
Celery Canvas Patterns
======================

Canvas primitives for orchestrating task workflows in a content publishing site.
Shows chain(), group(), chord(), and combinations.

Canvas primitives compose tasks into workflows:
- chain():  sequential pipeline, output of one feeds into the next
- group():  parallel execution, all tasks run independently
- chord():  parallel tasks with a callback that runs after all complete
- Combinations: nest primitives for complex workflows

All examples use the content publishing domain:
- Essay, FieldNote, ShelfEntry, Project, VideoProject
- Stages: research, drafting, production, published
"""

from celery import chain, chord, group, shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


# ===========================================================================
# Supporting tasks (used by the canvas patterns below)
# ===========================================================================

@shared_task
def fetch_essay_content(essay_id: int) -> dict:
    """Fetch essay content from the database."""
    from apps.content.models import Essay

    essay = Essay.objects.get(pk=essay_id)
    return {
        "essay_id": essay_id,
        "slug": essay.slug,
        "title": essay.title,
        "raw_content": essay.content,
        "stage": essay.stage,
    }


@shared_task
def parse_markdown_references(essay_data: dict) -> dict:
    """Parse internal references and footnotes from essay content."""
    from apps.content.services import extract_references

    refs = extract_references(essay_data["raw_content"])
    essay_data["references"] = refs
    essay_data["reference_count"] = len(refs)
    return essay_data


@shared_task
def render_to_static_markdown(essay_data: dict) -> dict:
    """Render final markdown with resolved references for the static site."""
    from apps.content.services import render_final_markdown

    rendered = render_final_markdown(
        content=essay_data["raw_content"],
        references=essay_data.get("references", []),
    )
    essay_data["rendered_markdown"] = rendered
    return essay_data


@shared_task
def store_rendered_output(essay_data: dict) -> str:
    """Save the rendered markdown back to the database and return the slug."""
    from apps.content.models import Essay

    Essay.objects.filter(pk=essay_data["essay_id"]).update(
        rendered_markdown=essay_data["rendered_markdown"],
        rendered_at=timezone.now(),
    )
    return essay_data["slug"]


@shared_task
def resize_image(image_id: int, dimensions: tuple) -> dict:
    """Resize a single image to the given dimensions."""
    from apps.content.models import EssayImage

    image = EssayImage.objects.get(pk=image_id)
    width, height = dimensions
    output_path = image.resize(width=width, height=height)
    return {
        "image_id": image_id,
        "dimensions": dimensions,
        "output_path": str(output_path),
    }


@shared_task
def upload_to_cdn(image_result: dict) -> dict:
    """Upload a processed image to the CDN."""
    from apps.content.services import cdn_upload

    cdn_url = cdn_upload(image_result["output_path"])
    image_result["cdn_url"] = cdn_url
    return image_result


@shared_task
def render_chapter(chapter_data: dict) -> dict:
    """Render a single chapter (essay or field note) to markdown."""
    from apps.content.services import render_final_markdown

    rendered = render_final_markdown(
        content=chapter_data["content"],
        references=chapter_data.get("references", []),
    )
    return {
        "slug": chapter_data["slug"],
        "title": chapter_data["title"],
        "rendered": rendered,
        "sort_order": chapter_data["sort_order"],
    }


@shared_task
def compile_book(chapter_results: list, project_id: int) -> dict:
    """
    Compile all rendered chapters into a single project bundle.

    This is the chord callback: it receives a list of results from all
    the parallel chapter rendering tasks.
    """
    from apps.content.models import Project

    project = Project.objects.get(pk=project_id)

    # Sort chapters by their original order.
    sorted_chapters = sorted(chapter_results, key=lambda c: c["sort_order"])

    bundle_content = "\n\n---\n\n".join(
        f"# {ch['title']}\n\n{ch['rendered']}" for ch in sorted_chapters
    )

    bundle_path = project.write_bundle(bundle_content)

    Project.objects.filter(pk=project_id).update(
        last_compiled_at=timezone.now(),
        chapter_count=len(sorted_chapters),
    )

    return {
        "project_slug": project.slug,
        "chapters_compiled": len(sorted_chapters),
        "bundle_path": str(bundle_path),
    }


@shared_task
def notify_compilation_complete(result: dict):
    """Send notification that a project compilation finished."""
    from apps.notifications.services import notify_subscribers

    notify_subscribers(
        event="project_compiled",
        data=result,
    )


@shared_task
def handle_workflow_error(request, exc, traceback):
    """
    Error callback for canvas workflows.

    Wire this into chain/chord with link_error to catch failures
    without losing track of them.
    """
    logger.error(
        "Workflow task %s failed: %s",
        request.id,
        exc,
        exc_info=True,
    )
    # In production: update a status model, send alert, etc.


# ===========================================================================
# Pattern 1: chain() -- Sequential processing pipeline
# ===========================================================================
# Each task's return value becomes the first argument of the next task.
# If any task fails, the chain stops and the error propagates.
#
# Pipeline: fetch -> parse references -> render -> store

def publish_essay_pipeline(essay_id: int):
    """
    Run the full essay publishing pipeline as a chain.

    chain() connects tasks sequentially. The return value of each task
    becomes the first argument of the next one.

    Usage:
        result = publish_essay_pipeline(42)
        slug = result.get()  # blocks until complete
    """
    workflow = chain(
        fetch_essay_content.s(essay_id),
        parse_markdown_references.s(),
        render_to_static_markdown.s(),
        store_rendered_output.s(),
    )

    # Add an error handler to the entire chain.
    return workflow.apply_async(link_error=handle_workflow_error.s())


# ===========================================================================
# Pattern 2: group() -- Parallel processing
# ===========================================================================
# All tasks in a group run concurrently. The group result is a list of
# individual results in the same order as the tasks.

def process_essay_images_parallel(essay_id: int):
    """
    Resize all images for an essay in parallel.

    group() runs all resize tasks concurrently. Each image gets resized
    to multiple dimensions at once.

    Usage:
        result = process_essay_images_parallel(42)
        all_results = result.get()  # list of dicts
    """
    from apps.content.models import EssayImage

    images = EssayImage.objects.filter(essay_id=essay_id, processed=False)

    target_dimensions = [
        (1200, 800),  # Full size
        (600, 400),   # Medium
        (300, 200),   # Thumbnail
    ]

    # Create a resize task for each image+dimension combination.
    resize_tasks = []
    for image in images:
        for dims in target_dimensions:
            resize_tasks.append(resize_image.s(image.id, dims))

    if not resize_tasks:
        logger.info("No unprocessed images for essay %d.", essay_id)
        return None

    workflow = group(resize_tasks)
    return workflow.apply_async()


def upload_resized_images_parallel(image_results: list):
    """
    Upload a batch of already-resized images to the CDN in parallel.

    Shows group() with pre-computed arguments.
    """
    upload_tasks = group(upload_to_cdn.s(result) for result in image_results)
    return upload_tasks.apply_async()


# ===========================================================================
# Pattern 3: chord() -- Fan-out / fan-in
# ===========================================================================
# chord = group + callback. Run N tasks in parallel, then call a single
# callback with all the results. The callback receives a list.
#
# Use case: render each chapter of a project in parallel, then compile
# them all into a single book bundle.

def compile_project(project_id: int):
    """
    Compile a project by rendering all chapters in parallel, then
    assembling them into a bundle.

    chord() = group of header tasks + a callback.
    The callback (compile_book) receives a list of all chapter results.

    Usage:
        result = compile_project(7)
        bundle_info = result.get()
    """
    from apps.content.models import Project

    project = Project.objects.prefetch_related("essays", "field_notes").get(
        pk=project_id,
    )

    # Build chapter data for each content item.
    chapters = []
    for i, essay in enumerate(project.essays.filter(stage="published")):
        chapters.append({
            "slug": essay.slug,
            "title": essay.title,
            "content": essay.content,
            "references": [],
            "sort_order": i,
        })

    for j, note in enumerate(project.field_notes.filter(stage="published")):
        chapters.append({
            "slug": note.slug,
            "title": note.title,
            "content": note.content,
            "references": [],
            "sort_order": len(chapters) + j,
        })

    if not chapters:
        logger.warning("Project %s has no published content.", project.slug)
        return None

    # Fan out: render each chapter in parallel.
    # Fan in: compile_book receives all rendered chapters.
    header = group(render_chapter.s(ch) for ch in chapters)

    # The callback's first argument is the list of header results.
    # Additional arguments are passed with .si() (immutable signature)
    # or as extra args.
    callback = compile_book.s(project_id=project_id)

    workflow = chord(header)(callback)
    return workflow


# ===========================================================================
# Pattern 4: Combining chain and group
# ===========================================================================
# Real workflows often mix sequential and parallel steps.
# Example: fetch -> (resize all images in parallel) -> upload -> notify

def full_essay_publish_workflow(essay_id: int):
    """
    Full publishing workflow combining chain, group, and chord.

    Step 1: Fetch and render essay content (chain).
    Step 2: Resize all images in parallel (group inside a chord).
    Step 3: Upload all images to CDN in parallel (group).
    Step 4: Send notification (final task in chain).

    This shows how to nest canvas primitives for complex workflows.
    """
    from apps.content.models import EssayImage

    # Step 1: Sequential content processing.
    content_pipeline = chain(
        fetch_essay_content.s(essay_id),
        parse_markdown_references.s(),
        render_to_static_markdown.s(),
        store_rendered_output.s(),
    )

    # Steps 2+3 would typically be triggered after step 1 completes.
    # Here we show the pattern for composing them.
    return content_pipeline.apply_async(
        link=send_publish_notification.s(),
        link_error=handle_workflow_error.s(),
    )


def process_and_upload_images(essay_id: int):
    """
    Process images: resize all dimensions in parallel, then upload
    each result to the CDN.

    Shows chain of groups: first group resizes, then the results
    feed into an upload step.
    """
    from apps.content.models import EssayImage

    images = EssayImage.objects.filter(essay_id=essay_id, processed=False)
    if not images.exists():
        return None

    dimensions = [(1200, 800), (600, 400), (300, 200)]

    # For each image, create a chain: resize -> upload.
    # Then group all those chains to run in parallel.
    image_chains = []
    for image in images:
        for dims in dimensions:
            image_chains.append(
                chain(
                    resize_image.s(image.id, dims),
                    upload_to_cdn.s(),
                )
            )

    # All resize-then-upload chains run in parallel.
    return group(image_chains).apply_async()


# ===========================================================================
# Pattern 5: Chord with error handling
# ===========================================================================
# Chord callbacks fail if any header task fails. Use link_error on
# the chord to handle partial failures gracefully.

@shared_task
def handle_compilation_error(request, exc, traceback, project_id: int = None):
    """Handle errors during project compilation."""
    from apps.content.models import Project

    logger.error(
        "Chapter rendering failed during project compilation: %s", exc
    )
    if project_id:
        Project.objects.filter(pk=project_id).update(
            compilation_error=str(exc)[:500],
            compilation_failed_at=timezone.now(),
        )


def compile_project_with_error_handling(project_id: int):
    """
    Same as compile_project but with explicit error handling.

    If any chapter rendering fails, handle_compilation_error runs
    instead of compile_book.
    """
    from apps.content.models import Project

    project = Project.objects.prefetch_related("essays").get(pk=project_id)
    chapters = [
        {
            "slug": e.slug,
            "title": e.title,
            "content": e.content,
            "references": [],
            "sort_order": i,
        }
        for i, e in enumerate(project.essays.filter(stage="published"))
    ]

    if not chapters:
        return None

    header = group(render_chapter.s(ch) for ch in chapters)
    callback = compile_book.s(project_id=project_id)

    # Apply the chord and attach an error callback.
    result = chord(header, body=callback).apply_async(
        link_error=handle_compilation_error.s(project_id=project_id),
    )
    return result
